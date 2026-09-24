"""Application settings loaded from environment variables.

Configuration is read exclusively from the environment (12-factor). A `.env`
file is used only for local development via python-dotenv and is never required
in containers.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
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

    # Redis-backed request rate limiting (per client IP + route bucket).
    # Disabled in tests by default so the suite is not throttled; enable in
    # production (and the dedicated rate-limit test) via env.
    rate_limit_enabled: bool = True
    # Failed-login attempts allowed per IP+account within the window before a
    # 429 is returned (on top of the per-account DB lockout above).
    rate_limit_login: int = 20
    rate_limit_register: int = 10
    rate_limit_password_reset: int = 10
    rate_limit_ai: int = 30
    rate_limit_window_seconds: int = 60

    # Double-submit CSRF token (cookie + X-CSRF-Token header on unsafe methods).
    csrf_enabled: bool = True
    csrf_cookie_name: str = "qloot_csrf"
    csrf_header_name: str = "X-CSRF-Token"

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
    # Embedding model + vector dimension for the material RAG index. The mock
    # provider produces deterministic vectors of ``ai_embedding_dim``; real
    # providers fail fast if the embedding model is not configured.
    ai_embedding_model: str = "text-embedding-3-small"
    ai_embedding_dim: int = 256
    ai_http_timeout_seconds: int = 60
    ai_max_upload_bytes: int = 10 * 1024 * 1024
    ai_max_questions: int = 20
    # Display name of the built-in study/career assistant.
    assistant_name: str = "Asisten Qlo"
    # Free AI requests granted per user before ORT is charged (1 request = 1 ORT).
    # Tracked per user in Redis (degrades to "no free tier" if Redis is down).
    ai_free_requests: int = 3

    # --- Blockchain --------------------------------------------------------
    chain_id: int = 31337
    blockchain_network: str = "localhost"
    sepolia_rpc_url: str = ""
    localhost_rpc_url: str = "http://127.0.0.1:8545"
    blockchain_private_key: str = ""
    etherscan_api_key: str = ""
    treasury_address: str = ""
    # Personal wallet pre-filled for every account; users may change their own
    # at /wallet (paste an address or connect MetaMask). Read from the
    # environment (DEFAULT_WALLET_ADDRESS) — never hardcode a real address here.
    default_wallet_address: str = ""
    # QLoot ships FOUR separate ERC-1155 UUPS contracts, each with its own address.
    #   OPT = OryphemToken (base currency, unlimited)
    #   QTC = QlootChain (premium asset, cap 1e15)
    #   ORT = OryphemIntelligence (AI credit, 1 request = 1 ORT)
    #   ORX = OryphemProxy (router: 1 ORT = 50 OPT, 1 QTC = 1000 OPT)
    opt_contract_address: str = ""
    qtc_contract_address: str = ""
    ort_contract_address: str = ""
    orx_contract_address: str = ""
    # OryphemProxy (ORX) rates, in OPT per 1 unit of the target asset.
    orx_ort_rate: int = 50
    orx_qtc_rate: int = 1000
    # Legacy alias (points at the OPT asset). Kept so older configs keep working.
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
    # OPT paid for milestone events (0 disables the payout). All are idempotent
    # per event via deterministic reward keys.
    reward_perfect_exam: int = 100
    reward_quiz_master: int = 30
    reward_course_completion: int = 50

    # --- Withdrawals -------------------------------------------------------
    # Withdrawals require admin approval before they are submitted on-chain.
    withdrawal_min_amount: int = 10
    withdrawal_max_amount: int = 1_000_000
    # Rolling 24h sum of requested+approved withdrawals per user.
    withdrawal_daily_limit: int = 5_000_000
    # Flat fee (in OPT) charged per withdrawal on top of the amount.
    withdrawal_fee: int = 0

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

    @model_validator(mode="after")
    def _guard_cross_site_without_csrf(self) -> Settings:
        # `SameSite=None` (cross-site cookies) without a token is unsafe: a
        # top-level cross-site POST would carry the session cookie. Refuse it.
        if self.session_same_site == "none" and not self.csrf_enabled:
            raise ValueError(
                "SESSION_SAME_SITE=none requires CSRF protection (set CSRF_ENABLED=true)"
            )
        return self

    @property
    def rpc_url(self) -> str:
        if self.blockchain_network == "sepolia":
            return self.sepolia_rpc_url
        return self.localhost_rpc_url

    def asset_address(self, key: str) -> str:
        """Address of a QLoot asset/router by key: OPT, QTC, ORT or ORX.

        Falls back to the legacy ``OPC_CONTRACT_ADDRESS`` for OPT so older
        configuration keeps working.
        """
        key = key.upper()
        mapping = {
            "OPT": self.opt_contract_address or self.opc_contract_address,
            "QTC": self.qtc_contract_address,
            "ORT": self.ort_contract_address,
            "ORX": self.orx_contract_address,
        }
        return mapping.get(key, "")

    # Static metadata of the three assets, keyed by asset code.
    ASSET_META: dict[str, dict[str, str]] = {
        "OPT": {
            "name": "OryphemToken",
            "symbol": "OPT",
            "role": "Mata uang dasar (diperoleh di sistem QLoot)",
        },
        "QTC": {
            "name": "QlootChain",
            "symbol": "QTC",
            "role": "Aset premium (sertifikat, pesan terenkripsi)",
        },
        "ORT": {
            "name": "OryphemIntelligence",
            "symbol": "ORT",
            "role": "Kredit AI (1 request = 1 ORT)",
        },
    }

    def orx_rate(self, asset: str) -> int:
        """OPT required to obtain 1 unit of `asset` (QTC or ORT)."""
        return self.orx_ort_rate if asset.upper() == "ORT" else self.orx_qtc_rate


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
