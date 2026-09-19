"""Unit tests for the blockchain client helpers (no live node required)."""

from __future__ import annotations

from app.blockchain.client import _b32, _stable_uint


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
