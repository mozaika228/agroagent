from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://agro:agro@localhost:5432/agroagent"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    ollama_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    langgraph_use_llm: bool = False
    retriever_vector_weight: float = 0.7
    retriever_bm25_weight: float = 0.3
    retriever_semantic_k: int = 40
    retriever_lexical_k: int = 40
    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_k: int = 30
    reranker_batch_size: int = 16
    web_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 1440
    max_upload_mb: int = 10
    max_requests_per_minute: int = 90
    redis_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_bot_admin_email: str | None = None
    telegram_bot_admin_password: str | None = None
    telegram_bot_api_base: str = "http://localhost:8000"


settings = Settings()
