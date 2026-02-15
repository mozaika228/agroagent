from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SafetyDecision:
    level: str
    action: str
    reasons: list[str]
    rules_triggered: list[str]
    safe_alternative: str


_BLOCKED_TERMS = {
    "paraquat": "Highly hazardous herbicide; do not provide handling instructions.",
    "methyl parathion": "Banned/extremely hazardous organophosphate pesticide.",
    "aldicarb": "Extremely toxic carbamate pesticide.",
    "endrin": "Persistent organic pollutant and highly hazardous pesticide.",
    "паракват": "Высокоопасный гербицид; рекомендации по применению блокируются.",
}

_WARN_TERMS = {
    "pesticide": "Pesticide use requires local regulation checks and PPE.",
    "herbicide": "Herbicide recommendations require dosage and safety verification.",
    "fungicide": "Fungicide recommendations require disease confirmation and label checks.",
    "инсектицид": "Проверьте регламенты, СИЗ и инструкцию по применению.",
    "гербицид": "Требуется проверка дозировки и локальных ограничений.",
    "фунгицид": "Нужна верификация диагноза и регламента применения.",
}


def evaluate_agro_policy(question: str, recommendation: str, locale: str = "ru") -> SafetyDecision:
    corpus = f"{question}\n{recommendation}".lower()
    reasons: list[str] = []
    rules: list[str] = []

    for term, reason in _BLOCKED_TERMS.items():
        if term in corpus:
            reasons.append(reason)
            rules.append(f"blocked_term:{term}")

    if rules:
        safe_alt = (
            "Recommendation blocked by safety policy. Use IPM approach, confirm diagnosis with agronomist, "
            "and follow approved local products and labels."
        )
        return SafetyDecision(
            level="high",
            action="block",
            reasons=reasons,
            rules_triggered=rules,
            safe_alternative=safe_alt,
        )

    for term, reason in _WARN_TERMS.items():
        if term in corpus:
            reasons.append(reason)
            rules.append(f"warning_term:{term}")

    if rules:
        return SafetyDecision(
            level="medium",
            action="warn",
            reasons=reasons,
            rules_triggered=rules,
            safe_alternative=recommendation,
        )

    return SafetyDecision(
        level="low",
        action="allow",
        reasons=["No blocked safety signals detected."],
        rules_triggered=[],
        safe_alternative=recommendation,
    )
