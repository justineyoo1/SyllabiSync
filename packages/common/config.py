from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Settings(BaseModel):
    endpoint_url: str = Field(..., description="S3-compatible endpoint URL, e.g., http://minio:9000")
    access_key: str = Field(..., description="S3 access key (MinIO access key)")
    secret_key: str = Field(..., description="S3 secret key (MinIO secret key)")
    bucket: str = Field(..., description="Default bucket to use for uploads")
    region: str = Field(default="us-east-1", description="Region for S3-compatible services")
    secure: bool = Field(default=False, description="Use HTTPS when connecting to endpoint")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="SyllabusSync", description="Application name")
    environment: str = Field(default="dev", description="Environment name: dev|staging|prod")
    log_level: str = Field(default="INFO", description="Logging level")

    # Database / Cache
    database_url: PostgresDsn = Field(..., alias="POSTGRES_DSN")
    redis_url: RedisDsn = Field(..., alias="REDIS_URL")

    # S3 / MinIO
    s3_endpoint_url: str = Field(..., alias="S3_ENDPOINT_URL")
    s3_access_key: str = Field(..., alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(..., alias="S3_SECRET_KEY")
    s3_bucket: str = Field(..., alias="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_secure: bool = Field(default=False, alias="S3_SECURE")

    # Security
    secret_key: str = Field(default="dev-secret", alias="SECRET_KEY")

    # Embeddings / LLM
    embedding_provider: str = Field(default="none", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    llm_provider: str = Field(default="none", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    @property
    def s3(self) -> S3Settings:
        return S3Settings(
            endpoint_url=self.s3_endpoint_url,
            access_key=self.s3_access_key,
            secret_key=self.s3_secret_key,
            bucket=self.s3_bucket,
            region=self.s3_region,
            secure=self.s3_secure,
        )

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper = v.upper()
        if upper not in valid:
            return "INFO"
        return upper


@lru_cache
def get_settings() -> AppSettings:
    """Return cached application settings loaded from environment/.env.

    Using LRU cache ensures a singleton-style settings object across the app.
    """
    return AppSettings()  # type: ignore[call-arg]


