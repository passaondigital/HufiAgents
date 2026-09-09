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
    poll_interval_seconds: float = Field(0.1, gt=0, le=5)
    routine_poll_interval_seconds: float = Field(30.0, gt=0, le=600)
    max_pending_tasks: int = Field(100, ge=1, le=10000)
    heartbeat_timeout_seconds: float = Field(120, gt=0)
    heartbeat_interval_seconds: float = Field(30, gt=0)
    model_timeout_seconds: float = Field(180, gt=0)
    tool_timeout_seconds: float = Field(30, gt=0, le=300)
    approval_timeout_seconds: float = Field(86400, gt=0)
    approval_token: SecretStr = SecretStr("")
    risk_policy_path: Path = Path("config/risk_policy.yaml")
    # Phase 2 git/PR workflow: empty (default) disables push/PR entirely. Never
    # taken from a task/agent-supplied param -- only Pascal's own config chooses
    # the destination, so a task can never redirect a push/PR to another target.
    git_remote_url: str = ""
    github_repo: str = ""
    github_base_branch: str = "main"
    github_token: SecretStr = SecretStr("")
    # Phase 2B project connector (ADR-010). A task selects a project by id;
    # repo_url/github_repo/commands always come from this file, never a task.
    projects_path: Path = Path("config/projects.yaml")
    # Clone/test/build/lint can legitimately run much longer than the quick
    # status/diff/commit/push calls tool_timeout_seconds already bounds, so
    # they get their own, larger, still-bounded budget.
    project_tool_timeout_seconds: float = Field(240, gt=0, le=1800)
    # V1 web UI/API login (hufiagents/auth.py, docs/DECISIONS.md ADR-015).
    # Both fields empty (default) disables auth entirely -- required so the
    # existing test suite, which never sets these, is unaffected. Only a
    # deployment that sets both gets a login-gated UI/API.
    admin_username: str = ""
    admin_password_hash: SecretStr = SecretStr("")
    session_secret: SecretStr = SecretStr("")
    # Only ever False for local HTTP testing before a TLS reverse proxy is in
    # front of the app; production always leaves this True (docs/V1-OPERATIONS.md).
    cookie_secure: bool = True
    # Bind/port for `hufiagents serve`. Host is intentionally not
    # configurable here -- V1 is always loopback-only; a reverse proxy
    # terminates TLS and is the only public listener (docs/V1-OPERATIONS.md).
    port: int = Field(8765, ge=1, le=65535)
    # Reverse proxy forwards the real Host header (e.g. agents.heyhufi.com)
    # to this loopback app -- TrustedHostMiddleware rejects anything not in
    # its allowlist, so a public deployment must add its own hostname here.
    # Empty (default) keeps the existing 127.0.0.1/localhost/testserver-only
    # allowlist, so nothing changes for local dev or the test suite.
    public_hostname: str = ""
    # V1.3 Browser configuration. browser_allow_localhost is False in production
    # to protect against SSRF; test fixtures explicitly enable it for local test servers.
    browser_headless: bool = True
    browser_allow_localhost: bool = False

    @model_validator(mode="after")
    def heartbeat_order(self):
        if self.heartbeat_interval_seconds >= self.heartbeat_timeout_seconds:
            raise ValueError("heartbeat interval must be shorter than timeout")
        return self

    @property
    def auth_enabled(self) -> bool:
        return bool(self.admin_username and self.admin_password_hash.get_secret_value())

    @model_validator(mode="after")
    def auth_configuration(self):
        # Fail at startup, not silently, if auth is half-configured (a
        # missing session_secret would make every issued session
        # unverifiable after a restart -- effectively a locked-out or, worse,
        # forgeable login).
        if self.admin_username and not self.admin_password_hash.get_secret_value():
            raise ValueError("admin_username set without admin_password_hash")
        if self.auth_enabled and not self.session_secret.get_secret_value():
            raise ValueError("auth is configured but session_secret is empty")
        return self
