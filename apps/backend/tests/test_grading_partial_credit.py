"""Partial-credit grading for fill-blank, matching and ordering (C29)."""

from __future__ import annotations

import pytest

from tests.helpers import register_actor

pytestmark = pytest.mark.integration


async def _exam(client) -> str:
    exam = await client.post(
        "/api/v1/exams",
        json={"title": "Partial Exam", "duration_minutes": 30, "max_attempts": 10},
    )
    exam_id = exam.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id


async def _add(client, exam_id, payload) -> dict:
    r = await client.post(f"/api/v1/exams/{exam_id}/questions", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def _attempt(client, exam_id, qid, answer) -> int:
    a = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a}/answers/{qid}", json={"answer_text": answer})
    s = await client.post(f"/api/v1/attempts/{a}/submit")
    assert s.status_code == 200, s.text
    return s.json()["score_bp"]


async def test_fill_blank_normalisation(client):
    await register_actor(client, "fb_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    q = await _add(
        client,
        exam_id,
        {
            "prompt": "Ibu kota Indonesia adalah ____.",
            "qtype": "fill_blank",
            "position": 0,
            "answer_json": {"accepted": ["Jakarta"], "case_sensitive": False, "trim": True},
        },
    )
    await client.post("/api/v1/auth/logout")
    await register_actor(client, "fb_student@ex.com", "student")

    # Case/space-insensitive match -> full credit.
    assert await _attempt(client, exam_id, q["id"], "  jaKaRta ") == 10000
    assert await _attempt(client, exam_id, q["id"], "Bandung") == 0


async def test_fill_blank_case_sensitive(client):
    await register_actor(client, "fb2_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    q = await _add(
        client,
        exam_id,
        {
            "prompt": "Simbol air adalah ____.",
            "qtype": "fill_blank",
            "answer_json": {"accepted": ["H2O"], "case_sensitive": True},
        },
    )
    await client.post("/api/v1/auth/logout")
    await register_actor(client, "fb2_student@ex.com", "student")
    assert await _attempt(client, exam_id, q["id"], "H2O") == 10000
    assert await _attempt(client, exam_id, q["id"], "h2o") == 0


async def test_ordering_partial_credit(client):
    await register_actor(client, "ord_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    q = await _add(
        client,
        exam_id,
        {
            "prompt": "Urutkan dari terkecil ke terbesar.",
            "qtype": "ordering",
            "position": 0,
            "answer_json": {"order": ["A", "B", "C", "D"]},
        },
    )
    await client.post("/api/v1/auth/logout")
    await register_actor(client, "ord_student@ex.com", "student")

    # All in place -> 100%.
    assert await _attempt(client, exam_id, q["id"], '["A","B","C","D"]') == 10000
    # One swapped (positions B<->C) -> 2/4 in place -> 50%.
    assert await _attempt(client, exam_id, q["id"], '["A","C","B","D"]') == 5000
    # Fully reversed -> nothing in place -> 0%.
    assert await _attempt(client, exam_id, q["id"], '["D","C","B","A"]') == 0
    # First item kept, rest wrong -> 1/4 = 25%.
    assert await _attempt(client, exam_id, q["id"], '["A","D","B","C"]') == 2500
    # All wrong -> 0%.
    assert await _attempt(client, exam_id, q["id"], '["B","A","D","C"]') == 0


async def test_matching_partial_credit(client):
    await register_actor(client, "mat_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    q = await _add(
        client,
        exam_id,
        {
            "prompt": "Cocokkan negara dengan ibu kotanya.",
            "qtype": "matching",
            "position": 0,
            "answer_json": {"pairs": {"ID": "Jakarta", "MY": "KL", "TH": "Bangkok"}},
        },
    )
    await client.post("/api/v1/auth/logout")
    await register_actor(client, "mat_student@ex.com", "student")

    # All correct -> 100%.
    assert (
        await _attempt(
            client, exam_id, q["id"], '{"ID":"Jakarta","MY":"KL","TH":"Bangkok"}'
        )
        == 10000
    )
    # Two of three -> 66.67% of max (3 pairs) -> 6667.
    assert (
        await _attempt(client, exam_id, q["id"], '{"ID":"Jakarta","MY":"KL","TH":"X"}')
        == 6667
    )
    # None correct -> 0%.
    assert (
        await _attempt(client, exam_id, q["id"], '{"ID":"X","MY":"Y","TH":"Z"}') == 0
    )


async def test_invalid_keys_rejected(client):
    await register_actor(client, "inv_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    # fill_blank without accepted.
    bad1 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Isian?", "qtype": "fill_blank"},
    )
    assert bad1.status_code == 422
    # ordering with < 2 items.
    bad2 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Urut?", "qtype": "ordering", "answer_json": {"order": ["A"]}},
    )
    assert bad2.status_code == 422
