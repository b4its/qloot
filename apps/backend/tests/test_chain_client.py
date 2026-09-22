"""Unit tests for the blockchain client helpers (no live node required)."""

from __future__ import annotations

from app.blockchain.client import ChainClient, _b32, _stable_uint
from app.core.config import settings


def test_b32_hashes_non_hex_strings():
    """Reasons like 'reward' must be encoded deterministically, not crash."""
    a = _b32("reward")
    b = _b32("reward")
    assert a == b
    assert len(a) == 32
    assert _b32("quest") != _b32("reward")


def test_b32_passthrough_for_32_byte_hex():
    hex32 = "0x" + "aa" * 32
    assert _b32(hex32) == bytes.fromhex("aa" * 32)
    assert len(_b32(hex32)) == 32


def test_b32_handles_arbitrary_text():
    assert len(_b32("hello world")) == 32
    # A short hex-looking string that is not 32 bytes is hashed, not parsed.
    assert len(_b32("0xdeadbeef")) == 32


def test_stable_uint_is_deterministic_and_in_range():
    v1 = _stable_uint("quest:1|user:1")
    v2 = _stable_uint("quest:1|user:1")
    assert v1 == v2
    assert 0 <= v1 < (1 << 256)
    assert _stable_uint("a") != _stable_uint("b")


def test_status_hides_addresses_by_default(monkeypatch):
    """The public status must not carry contract/treasury addresses."""
    monkeypatch.setattr(settings, "opt_contract_address", "0x" + "11" * 20)
    monkeypatch.setattr(settings, "treasury_address", "0x" + "22" * 20)
    status = ChainClient().status()
    assert "contract_address" not in status
    assert "treasury_address" not in status
    assert "assets" not in status
    assert {"dry_run", "network", "chain_id", "token_id", "confirmations_required"} <= set(status)


def test_admin_status_includes_all_assets(monkeypatch):
    opt = "0x" + "11" * 20
    qtc = "0x" + "33" * 20
    ort = "0x" + "44" * 20
    orx = "0x" + "55" * 20
    treasury = "0x" + "22" * 20
    monkeypatch.setattr(settings, "opt_contract_address", opt)
    monkeypatch.setattr(settings, "qtc_contract_address", qtc)
    monkeypatch.setattr(settings, "ort_contract_address", ort)
    monkeypatch.setattr(settings, "orx_contract_address", orx)
    monkeypatch.setattr(settings, "treasury_address", treasury)
    status = ChainClient().admin_status()
    # Legacy single-contract field = OPT.
    assert status["contract_address"] == opt
    assert status["treasury_address"] == treasury
    # Full multi-contract map.
    assert status["assets"]["OPT"]["address"] == opt
    assert status["assets"]["QTC"]["address"] == qtc
    assert status["assets"]["ORT"]["address"] == ort
    assert status["assets"]["ORX"]["address"] == orx
    assert status["assets"]["OPT"]["symbol"] == "OPT"


def test_asset_address_falls_back_to_legacy_opc_alias(monkeypatch):
    """OPC_CONTRACT_ADDRESS is a legacy alias for OPT."""
    monkeypatch.setattr(settings, "opt_contract_address", "")
    monkeypatch.setattr(settings, "opc_contract_address", "0x" + "ab" * 20)
    assert settings.asset_address("OPT") == "0x" + "ab" * 20


def test_dry_run_when_no_contract_configured(monkeypatch):
    monkeypatch.setattr(settings, "opt_contract_address", "")
    monkeypatch.setattr(settings, "opc_contract_address", "")
    monkeypatch.setattr(settings, "blockchain_dry_run", True)
    assert ChainClient().dry_run is True
