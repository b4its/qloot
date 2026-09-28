"""Storage hardening: key building, presigning and the AV hook (C36)."""

from __future__ import annotations

import uuid

from app.services import storage as storage_mod
from app.services.storage import build_key


def test_build_key_forces_pdf_and_is_path_safe():
    owner = uuid.uuid4()
    # A crafted filename must not escape the materials prefix or add a weird ext.
    key = build_key(owner, "../../etc/passwd.txt")
    assert key.startswith(f"materials/{owner}/")
    assert key.endswith(".pdf")
    assert ".." not in key
    assert "passwd" not in key


def test_build_key_defaults_pdf_without_extension():
    key = build_key(uuid.uuid4(), "noext")
    assert key.endswith(".pdf")


def test_local_storage_has_no_presigned_url(monkeypatch):
    monkeypatch.setattr(storage_mod.settings, "use_local_storage", True)
    s = storage_mod.Storage()
    assert s.use_local is True
    assert s.presigned_get_url("materials/x/y.pdf") is None


def test_minio_presign_returns_url(monkeypatch):
    """When MinIO is configured, presign returns a URL."""
    captured = {}

    class FakeMinio:
        def presigned_get_object(self, bucket, key, expires=None):
            captured["bucket"] = bucket
            captured["key"] = key
            return f"https://minio.example/{bucket}/{key}?sig=abc"

    monkeypatch.setattr(storage_mod.settings, "use_local_storage", False)
    monkeypatch.setattr(storage_mod.Storage, "_init_minio", lambda self: None)
    s = storage_mod.Storage()
    s._client = FakeMinio()  # type: ignore[assignment]
    url = s.presigned_get_url("materials/a/b.pdf", expires_seconds=120)
    assert url is not None and url.startswith("https://minio.example/")
    assert captured["key"] == "materials/a/b.pdf"


def test_av_hook_defaults_to_accept_clean_pdf():
    from app.services.storage import scan_for_viruses

    assert scan_for_viruses(b"%PDF-1.4 whatever") is True


def test_av_hook_rejects_eicar_signature():
    from app.services.storage import scan_for_viruses

    eicar = b"%PDF-1.4 X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    assert scan_for_viruses(eicar) is False


def test_av_hook_can_be_disabled_explicitly(monkeypatch):
    from app.services import storage as storage_mod

    monkeypatch.setattr(storage_mod.settings, "av_scanner", "disabled")
    assert storage_mod.scan_for_viruses(b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE") is True


def test_av_hook_clamav_mode_fails_closed(monkeypatch):
    from app.services import storage as storage_mod

    monkeypatch.setattr(storage_mod.settings, "av_scanner", "clamav")
    # A real scanner name without a wired client must reject, never accept.
    assert storage_mod.scan_for_viruses(b"%PDF-1.4 clean-looking") is False


def test_av_hook_custom_deny_signature(monkeypatch):
    from app.services import storage as storage_mod

    monkeypatch.setattr(storage_mod.settings, "av_scanner", "eicar")
    monkeypatch.setattr(storage_mod.settings, "av_deny_signature", "MALWARE-XYZ")
    assert storage_mod.scan_for_viruses(b"%PDF-1.4 MALWARE-XYZ payload") is False
    assert storage_mod.scan_for_viruses(b"%PDF-1.4 benign") is True

