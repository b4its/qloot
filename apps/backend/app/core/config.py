"""Application settings loaded from environment variables.

Configuration is read exclusively from the environment (12-factor). A `.env`
file is used only for local development via python-dotenv and is never required
in containers.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---------------------------------------------------------------
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "QLoot"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # --- Database ----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://qloot:change-me@localhost:5432/qloot"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # --- Redis -------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # --- Sessions / auth ---------------------------------------------------
    session_secret: str = "change-me"
    session_cookie_name: str = "qloot_session"
    session_secure: bool = False
    session_same_site: Literal["lax", "strict", "none"] = "lax"
    session_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    session_cookie_domain: str | None = None

    # Rate limiting / lockout
    login_max_attempts: int = 10
    login_lockout_seconds: int = 900

    # --- CORS --------------------------------------------------------------
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- AI ----------------------------------------------------------------
    # "openai" = any OpenAI-compatible /chat/completions endpoint (DeepSeek,
    # local gateways, etc.). "gemini" = Google REST. "mock" = offline simulation.
    ai_provider: Literal["mock", "gemini", "openai"] = "mock"
    gemini_api_key: str = ""
    # OpenAI-compatible endpoint (used when ai_provider == "openai").
    # Defaults to the Docker host gateway so a gateway on the host is reachable
    # from inside containers.
    ai_base_url: str = "http://host.docker.internal:20128/v1"
    ai_api_key: str = ""
    ai_generation_model: str = "gemini-2.0-flash"
    ai_scoring_model: str = "gemini-2.0-flash"
    ai_http_timeout_seconds: int = 60
    ai_max_upload_bytes: int = 10 * 1024 * 1024
    ai_max_questions: int = 20
    # Display name of the built-in study/career assistant.
    assistant_name: str = "Asisten Qlo"

    # --- Blockchain --------------------------------------------------------
    chain_id: int = 31337
    blockchain_network: str = "localhost"
    sepolia_rpc_url: str = ""
    localhost_rpc_url: str = "http://127.0.0.1:8545"
    blockchain_private_key: str = ""
    etherscan_api_key: str = ""
    treasury_address: str = ""
    # Default personal wallet address pre-filled for every account; users may
    # change their own at /wallet (paste an address or connect MetaMask).
    default_wallet_address: str = "0x6EdcA860c066FCdA6c434095d5901810DCE12b48"
    opc_contract_address: str = ""
    opc_token_id: int = 0
    opc_confirmations: int = 2
    opc_max_reward_per_tx: int = 100_000
    blockchain_dry_run: bool = True
    blockchain_poll_seconds: int = 5
    # AI worker cadence + stuck-job recovery window (seconds).
    worker_poll_seconds: int = 3
    worker_job_timeout_seconds: int = 900

    # --- Object storage ----------------------------------------------------
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "qloot-materials"
    minio_secure: bool = False
    storage_local_dir: str = "./.storage"
    use_local_storage: bool = True

    # --- Observability -----------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = True
    service_name: str = "qloot-backend"

    # --- Reward policy -----------------------------------------------------
    default_top_n_winners: int = 3
    reward_ranks: Annotated[list[int], NoDecode] = Field(default_factory=lambda: [100, 60, 40])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                return v
            return [item.strip() for item in s.split(",") if item.strip()]
        return v

    @field_validator("reward_ranks", mode="before")
    @classmethod
    def _split_int_csv(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                return v
            return [int(item) for item in s.split(",") if item.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def rpc_url(self) -> str:
        if self.blockchain_network == "sepolia":
            return self.sepolia_rpc_url
        return self.localhost_rpc_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
