from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .config import settings

logger = logging.getLogger("agroagent.telegram")

_token_lock = asyncio.Lock()
_api_token: str | None = None


async def _login() -> str:
    if not settings.telegram_bot_admin_email or not settings.telegram_bot_admin_password:
        raise RuntimeError("TELEGRAM_BOT_ADMIN_EMAIL and TELEGRAM_BOT_ADMIN_PASSWORD must be set")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{settings.telegram_bot_api_base.rstrip('/')}/v1/auth/login",
            json={"email": settings.telegram_bot_admin_email, "password": settings.telegram_bot_admin_password},
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["access_token"])


async def _get_api_token() -> str:
    global _api_token
    async with _token_lock:
        if _api_token is None:
            _api_token = await _login()
        return _api_token


async def _call_debate(question: str, locale: str = "ru") -> dict[str, Any]:
    token = await _get_api_token()
    async with httpx.AsyncClient(timeout=40.0) as client:
        resp = await client.post(
            f"{settings.telegram_bot_api_base.rstrip('/')}/v1/agents/debate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "question": question,
                "locale": locale,
                "include_steps": False,
                "rounds": 2,
            },
        )
        if resp.status_code == 401:
            # Refresh token once.
            async with _token_lock:
                _api_token = await _login()
            return await _call_debate(question, locale)
        resp.raise_for_status()
        return resp.json()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    await update.message.reply_text(
        "AgroAgent bot online. Ask a question about crops, weather, or agronomy in WKO."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    await update.message.reply_text("Send a question and I will return a recommendation.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    if update.message is None or not update.message.text:
        return
    question = update.message.text.strip()
    if not question:
        return
    await update.message.chat.send_action("typing")
    try:
        data = await _call_debate(question)
        answer = data.get("answer") or "No answer generated."
        safety = data.get("safety", {})
        suffix = f"\n\nSafety: {safety.get('effective_action', 'n/a')} ({safety.get('level', 'n/a')})"
        await update.message.reply_text(f"{answer}{suffix}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram handler failed: %s", exc)
        await update.message.reply_text("Error contacting AgroAgent API.")


def run_bot() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    run_bot()
