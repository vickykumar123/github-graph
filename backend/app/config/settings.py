from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # MongoDB settings
    mongodb_url: str
    database_name: str = "github_explorer"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 9999
    debug: bool = True
    env: str = "development"

    # AI Configuration (for automatic summary generation)
    ai_api_key: Optional[str] = None
    ai_provider: str = "openai"
    ai_model: str = "gpt-4o-mini"

    # Embedding Configuration
    use_codebert: bool = False  # False = use provider embeddings (prod), True = use local CodeBERT (dev)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

settings = Settings()
