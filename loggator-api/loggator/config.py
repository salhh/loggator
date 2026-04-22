from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://loggator:loggator@localhost:5432/loggator"

    # OpenSearch
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_auth_type: Literal["none", "basic", "api_key", "aws_iam"] = "none"
    opensearch_username: str = ""
    opensearch_password: str = ""
    opensearch_api_key: str = ""
    opensearch_use_ssl: bool = False
    opensearch_verify_certs: bool = True
    opensearch_ca_certs: str = ""
    opensearch_index_pattern: str = "logs-*"
    # AWS IAM
    aws_region: str = "us-east-1"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_concurrency: int = 3
    ollama_timeout: int = 120

    # LLM provider abstraction
    llm_provider: Literal["ollama", "anthropic", "openai"] = "ollama"
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = ""   # optional, for OpenAI-compatible endpoints
    openai_model: str = "gpt-4o-mini"
    llm_concurrency: int = 3
    llm_timeout: int = 120

    # Pipeline
    batch_interval_minutes: int = 15
    batch_window_minutes: int = 15
    streaming_poll_interval_seconds: int = 10
    streaming_batch_size: int = 500
    chunk_max_tokens: int = 3000

    # Alerts
    alert_severity_threshold: Literal["low", "medium", "high"] = "medium"
    slack_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    alert_from_email: str = ""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_rate_limit: str = "60/minute"


settings = Settings()
