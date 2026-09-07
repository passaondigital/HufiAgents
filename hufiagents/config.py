from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HUFI_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./run/hufiagents.sqlite3"
    workspace_root: Path = Path("workspaces")
    default_provider: str = "hufi-local-router"
    local_router_base_url: str = "http://127.0.0.1:8090/v1"
    local_model: str = "hufi-qwen9-fast"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    max_concurrent_tasks: int = Field(2, ge=1, le=8)
    max_pending_tasks: int = Field(100, ge=1, le=10000)
    heartbeat_timeout_seconds: float = Field(120, gt=0)
    heartbeat_interval_seconds: float = Field(30, gt=0)
    model_timeout_seconds: float = Field(180, gt=0)
    tool_timeout_seconds: float = Field(30, gt=0, le=300)
    approval_timeout_seconds: float = Field(86400, gt=0)
    approval_token: SecretStr = SecretStr("")
    risk_policy_path: Path = Path("config/risk_policy.yaml")

    @model_validator(mode="after")
    def heartbeat_order(self):
        if self.heartbeat_interval_seconds >= self.heartbeat_timeout_seconds:
            raise ValueError("heartbeat interval must be shorter than timeout")
        return self
