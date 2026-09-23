"""Regression tests for the 'complete every feature' hardening pass.

Covers:
  - private-room read visibility (members/owner/admin only; otherwise 404)
  - room participants/live carry a human display name
  - withdrawal destination addresses are validated like PATCH /wallet/address
  - previously-untyped endpoints now return a typed, validated shape
  - UserOut exposes last_login_at
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Completeness User")


async def _make_room(client, *, name="Room", is_public=True):
    r = await client.post("/api/v1/rooms", json={"name": name, "is_public": is_public})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --- room visibility ------------------------------------------------------
async def test_private_room_get_is_hidden_from_non_members(client):
    await _register(client, "room_owner@ex.com")
    room_id = await _make_room(client, name="Private", is_public=False)
    await client.post("/api/v1/auth/logout")

    # A different, unrelated user must not see a private room by id.
    await _register(client, "room_stranger@ex.com", "student")
    denied = await client.get(f"/api/v1/rooms/{room_id}")
    assert denied.status_code == 404, denied.text
    # Participants / events / live are hidden too (never leak the roster).
    assert (await client.get(f"/api/v1/rooms/{room_id}/participants")).status_code == 404
    assert (await client.get(f"/api/v1/rooms/{room_id}/events")).status_code == 404
    assert (await client.get(f"/api/v1/rooms/{room_id}/live")).status_code == 404


async def test_private_room_is_visible_to_owner_and_members(client):
    await _register(client, "room_owner2@ex.com")
    room_id = await _make_room(client, name="Private2", is_public=False)
    inv = await client.post(f"/api/v1/rooms/{room_id}/invite", json={"email": "member@example.com"})
    code = inv.json()["code"]
    # Owner can read their own private room.
    assert (await client.get(f"/api/v1/rooms/{room_id}")).status_code == 200
    await client.post("/api/v1/auth/logout")

    # A member who accepted the invite can read it.
    await _register(client, "room_member@ex.com", "student")
    accepted = await client.post("/api/v1/rooms/invitations/accept", json={"code": code})
    assert accepted.status_code == 200, accepted.text
    ok = await client.get(f"/api/v1/rooms/{room_id}")
    assert ok.status_code == 200, ok.text


async def test_public_room_is_visible_to_anyone(client):
    await _register(client, "pub_owner@ex.com")
    room_id = await _make_room(client, name="Public", is_public=True)
    await client.post("/api/v1/auth/logout")

    await _register(client, "pub_viewer@ex.com", "student")
    ok = await client.get(f"/api/v1/rooms/{room_id}")
    assert ok.status_code == 200, ok.text


async def test_room_participants_carry_display_name(client):
    me = await _register(client, "named_owner@ex.com")
    room_id = await _make_room(client, name="Named Room")
    parts = await client.get(f"/api/v1/rooms/{room_id}/participants")
    assert parts.status_code == 200, parts.text
    body = parts.json()
    assert body, "owner should be a participant"
    # The owner's display name is surfaced (never just a bare UUID).
    assert any(p["display_name"] == me["full_name"] for p in body)
    live = await client.get(f"/api/v1/rooms/{room_id}/live")
    assert live.status_code == 200, live.text
    assert all("display_name" in entry for entry in live.json())


# --- withdrawal address validation ---------------------------------------
async def test_withdrawal_rejects_malformed_destination_address(client):
    await _register(client, "wd_student@ex.com", "student")
    # A 42-char string that is not hex must be rejected at validation time.
    bad = await client.post(
        "/api/v1/wallet/withdrawals",
        json={"amount": 1, "destination_address": "0x" + "z" * 40},
    )
    assert bad.status_code == 422, bad.text


async def test_withdrawal_accepts_valid_address(client):
    await _register(client, "wd_student2@ex.com", "student")
    # Even with zero balance the *address* must validate; the failure is then a
    # business error (insufficient balance), proving it passed validation.
    ok = await client.post(
        "/api/v1/wallet/withdrawals",
        json={"amount": 1, "destination_address": "0x" + "a" * 40},
    )
    assert ok.status_code == 409, ok.text  # insufficient balance, not 422


# --- typed responses ------------------------------------------------------
async def test_counselors_endpoint_returns_typed_shape(client):
    await _register(client, "career_student@ex.com", "student")
    r = await client.get("/api/v1/career/counselors")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body and {"name", "role", "focus"} <= set(body[0])


async def test_transfer_recipients_endpoint_returns_typed_shape(client):
    await _register(client, "xfer_a@ex.com", "student")
    await client.post("/api/v1/auth/logout")
    await _register(client, "xfer_b@ex.com", "student")
    r = await client.get("/api/v1/wallet/transfer-recipients")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body and {"user_id", "full_name", "email"} <= set(body[0])


async def test_user_out_exposes_last_login(client):
    me = await _register(client, "login_time@ex.com", "student")
    # Freshly registered => the field must exist (may be null).
    assert "last_login_at" in me
    await client.post("/api/v1/auth/logout")
    logged = await client.post(
        "/api/v1/auth/login", json={"email": "login_time@ex.com", "password": "Password123!"}
    )
    assert logged.status_code == 200, logged.text
    assert logged.json()["last_login_at"] is not None


# --- quest ranking real opc_earned ---------------------------------------
async def test_quest_ranking_reports_real_reward(client):
    """After a quest is finalized its ranking must surface the winner's actual
    reward amount (previously hardcoded to 0). Fully API-driven so no raw
    session/commit is needed."""
    # Teacher + a published multiple-choice exam (MC grades instantly, so the
    # quest attempt is recorded at submit time without needing a worker).
    await _register(client, "q_owner@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "Quest Exam", "duration_minutes": 15})
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Ibu kota Indonesia?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "Jakarta", "is_correct": True},
                {"text": "Bandung", "is_correct": False},
            ],
        },
    )
    qid = q.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")

    # Quest linked to that exam; rank 1 pays 123 OPT.
    quest = await client.post(
        "/api/v1/quests",
        json={
            "title": "Rewarded Quest",
            "exam_id": exam_id,
            "top_n_winners": 1,
            "rules": [{"rank": 1, "reward_amount": 123}],
        },
    )
    assert quest.status_code == 201, quest.text
    quest_id = quest.json()["id"]
    assert (await client.post(f"/api/v1/quests/{quest_id}/publish")).status_code == 200
    await client.post("/api/v1/auth/logout")

    # Student takes and submits the exam.
    await _register(client, "q_winner@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    submitted = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submitted.status_code == 200, submitted.text
    await client.post("/api/v1/auth/logout")

    # Teacher finalizes => the reward allocation is created for the winner.
    await client.post(
        "/api/v1/auth/login", json={"email": "q_owner@ex.com", "password": "Password123!"}
    )
    fin = await client.post(f"/api/v1/quests/{quest_id}/finalize")
    assert fin.status_code == 200, fin.text
    assert fin.json()["allocations_created"] == 1, fin.text

    # The public ranking exposes the real reward, not a hardcoded 0.
    ranking = await client.get(f"/api/v1/rankings/quests/{quest_id}")
    assert ranking.status_code == 200, ranking.text
    entries = ranking.json()["entries"]
    assert entries, ranking.text
    top = entries[0]
    assert top["score_bp"] == 10000
    assert top["opc_earned"] == 123, ranking.text
    assert top["display_name"] == "Completeness User"
