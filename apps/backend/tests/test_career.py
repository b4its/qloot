"""Tests for the career guidance module (simulated)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Career User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_academic_dashboard_empty_then_with_grades(client):
    await _register(client, "career_dash@ex.com")
    d0 = await client.get("/api/v1/career/dashboard")
    assert d0.status_code == 200
    assert d0.json()["average"] == 0

    for subject, grade in [("Fisika", 92), ("Matematika", 85), ("Kimia", 64), ("B. Inggris", 78)]:
        r = await client.post("/api/v1/career/grades", json={"subject": subject, "grade": grade})
        assert r.status_code == 200, r.text

    d = await client.get("/api/v1/career/dashboard")
    body = d.json()
    assert body["average"] > 0
    assert body["strong_subject"] == "Fisika"
    assert body["weak_subject"] == "Kimia"
    assert len(body["trend"]) == 6
    assert len(body["radar"]) == 6
    assert len(body["insights"]) >= 1


async def test_personality_scoring_and_recommendation_engine(client):
    await _register(client, "career_rec@ex.com")
    for subject, grade in [("Fisika", 92), ("Matematika", 90), ("Kimia", 70), ("B. Inggris", 80)]:
        await client.post("/api/v1/career/grades", json={"subject": subject, "grade": grade})

    # Big Five: 20 answers (mostly high, some low) -> deterministic 0-100 traits.
    answers = [5, 5, 3, 4, 2] * 4
    p = await client.post("/api/v1/career/personality", json={"answers": answers})
    assert p.status_code == 200, p.text
    traits = p.json()
    for k in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
        assert 0 <= traits[k] <= 100
    assert traits["summary"]

    gen = await client.post("/api/v1/career/recommendations/generate")
    assert gen.status_code == 200, gen.text
    recs = gen.json()
    assert len(recs) == 3
    # Ranked descending by fit score.
    fits = [r["fit_score"] for r in recs]
    assert fits == sorted(fits, reverse=True)
    assert recs[0]["universities"]


async def test_recommendation_review_and_roadmap_activation(client):
    await _register(client, "career_road@ex.com")
    for subject, grade in [("Fisika", 90), ("Matematika", 88), ("B. Inggris", 80)]:
        await client.post("/api/v1/career/grades", json={"subject": subject, "grade": grade})
    await client.post("/api/v1/career/personality", json={"answers": [5, 4, 3, 4, 2] * 3})
    await client.post("/api/v1/career/recommendations/generate")

    sub = await client.post("/api/v1/career/recommendations/submit")
    assert sub.status_code == 200

    roadmap_before = await client.get("/api/v1/career/roadmap")
    assert roadmap_before.json() == []

    appr = await client.post("/api/v1/career/recommendations/approve")
    assert appr.status_code == 200

    roadmap = await client.get("/api/v1/career/roadmap")
    assert roadmap.status_code == 200
    milestones = roadmap.json()
    assert len(milestones) == 3
    assert milestones[0]["status"] == "in_progress"

    # Update progress.
    mid = milestones[0]["id"]
    upd = await client.patch(f"/api/v1/career/roadmap/{mid}", json={"progress_percent": 100})
    assert upd.status_code == 200
    assert upd.json()["status"] == "completed"


async def test_consultation_booking_and_cancel(client):
    await _register(client, "career_bk@ex.com")
    counselors = await client.get("/api/v1/career/counselors")
    assert counselors.status_code == 200
    assert len(counselors.json()) >= 1

    created = await client.post(
        "/api/v1/career/consultations",
        json={
            "counselor": "Bu Ratna Wijaya",
            "topic": "Pemilihan jurusan",
            "notes": "butuh arahan",
        },
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]
    assert created.json()["status"] == "pending"

    listed = await client.get("/api/v1/career/consultations")
    assert any(c["id"] == cid for c in listed.json())

    cancelled = await client.post(f"/api/v1/career/consultations/{cid}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_resource_library_categories(client):
    await _register(client, "career_lib@ex.com")
    all_items = await client.get("/api/v1/career/resources")
    assert all_items.status_code == 200
    items = all_items.json()
    assert len(items) >= 6
    cats = {i["category"] for i in items}
    assert {"course", "extracurricular", "material"}.issubset(cats)

    courses = await client.get("/api/v1/career/resources?category=course")
    assert all(i["category"] == "course" for i in courses.json())


async def test_assistant_rule_based_replies(client):
    await _register(client, "career_chat@ex.com")
    for msg, token in [
        ("Bedanya SNBP dan SNBT?", "SNBP"),
        ("Prospek ilmu komputer?", "Ilmu Komputer"),
        ("universitas terbaik untuk teknik", "ITB"),
        ("siapa kamu?", "QLoot"),
    ]:
        r = await client.post("/api/v1/career/assistant", json={"message": msg})
        assert r.status_code == 200, r.text
        assert token.lower() in r.json()["answer"].lower()
        assert 0 <= r.json()["confidence_bp"] <= 10000
