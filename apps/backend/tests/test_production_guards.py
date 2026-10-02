"""Production fail-closed and chain-invariant guards (W4).

Pure unit tests: they construct Settings directly and assert the validators
refuse unsafe production configurations, and that the chain client reports
coherent custody invariants in dry-run.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings


def _prod(**over) -> dict:
    base = {
        "app_env": "production",
        "session_secret": "a-strong-unique-secret-value",
        "database_url": "postgresql+asyncpg://qloot:realpass@db:5432/qloot",
        "blockchain_dry_run": True,
        "opt_contract_address": "",
        "treasury_address": "",
        "blockchain_private_key": "",
    }
    base.update(over)
    return base


def test_production_refuses_placeholder_session_secret():
    with pytest.raises(ValueError, match="SESSION_SECRET"):
        Settings(**_prod(session_secret="change-me"))


def test_production_refuses_placeholder_database_password():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            **_prod(database_url="postgresql+asyncpg://qloot:change-me@db:5432/qloot"),
        )


def test_production_live_chain_requires_full_configuration():
    with pytest.raises(ValueError, match="Live chain"):
        Settings(**_prod(blockchain_dry_run=False))


def test_production_live_chain_accepts_complete_configuration():
    settings = Settings(
        **_prod(
            blockchain_dry_run=False,
            opt_contract_address="0x" + "1" * 40,
            treasury_address="0x" + "2" * 40,
            blockchain_private_key="0x" + "3" * 64,
        )
    )
    assert settings.is_production
    assert settings.asset_address("OPT").startswith("0x")


def test_development_keeps_placeholder_defaults():
    # Non-production must remain friction-free for offline demo/testing: the
    # production fail-closed rules simply do not apply.
    settings = Settings(app_env="development")
    assert not settings.is_production


def test_dry_run_reports_coherent_invariants():
    from app.blockchain.client import ChainClient

    client = ChainClient()
    assert client.dry_run
    checks = client.verify_invariants()
    assert checks, "invariants must return rows"
    # Dry-run demo must look coherent: contract config and treasury rows are
    # informational (ok=true) so an offline deployment is not misleadingly red.
    keys = {c["key"]: c for c in checks}
    assert keys["OPT_contract_configured"]["ok"]
    assert keys["treasury_configured"]["ok"]
    assert keys["signer_has_minter_role"]["ok"]
    for row in checks:
        assert {"key", "ok", "detail"} <= set(row)
