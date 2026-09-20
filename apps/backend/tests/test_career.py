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
    # Trend is derived from the actual graded terms (one term here).
    assert len(body["trend"]) == 1
    assert body["trend"][0]["month"] == "2025/2026-genap"
    assert len(body["radar"]) == 6
    assert len(body["insights"]) >= 1
    # Strong subject drives the "potential" insight (not a hardcoded claim).
    potential = next(i for i in body["insights"] if i["kind"] == "potential")
    assert "Fisika" in potential["title"] or "Fisika" in potential["detail"]


async def test_dashboard_uses_latest_term_and_real_trend(client):
    await _register(client, "career_terms@ex.com")
    # Two terms for Matematika: the later (genap) value must win deterministically.
    await client.post(
        "/api/v1/career/grades",
        json={"subject": "Matematika", "grade": 60, "term": "2024/2025-ganjil"},
    )
    await client.post(
        "/api/v1/career/grades",
        json={"subject": "Matematika", "grade": 90, "term": "2024/2025-genap"},
    )
    await client.post(
        "/api/v1/career/grades",
        json={"subject": "Fisika", "grade": 70, "term": "2024/2025-genap"},
    )

    body = (await client.get("/api/v1/career/dashboard")).json()
    # One row per subject, latest term only.
    subjects = {s["subject"]: s["grade"] for s in body["subjects"]}
    assert subjects["Matematika"] == 90
    # Trend has one point per distinct term, chronological.
    assert [t["month"] for t in body["trend"]] == ["2024/2025-ganjil", "2024/2025-genap"]


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


async def test_single_grade_does_not_contradict_itself(client):
    await _register(client, "career_single@ex.com")
    await client.post("/api/v1/career/grades", json={"subject": "Fisika", "grade": 88})
    body = (await client.get("/api/v1/career/dashboard")).json()
    assert body["strong_subject"] == body["weak_subject"] == "Fisika"
    kinds = {i["kind"] for i in body["insights"]}
    # With a single subject we must not emit both consistency and attention.
    assert not ({"consistency", "attention"} <= kinds)


async def test_recommender_is_deterministic_under_multi_term_grades(client):
    await _register(client, "career_det@ex.com")
    # Same subject across terms: the recommender must use the latest term only,
    # independent of insertion order.
    await client.post(
        "/api/v1/career/grades",
        json={"subject": "Matematika", "grade": 95, "term": "2025/2026-genap"},
    )
    await client.post(
        "/api/v1/career/grades",
        json={"subject": "Matematika", "grade": 40, "term": "2024/2025-ganjil"},
    )
    await client.post("/api/v1/career/personality", json={"answers": [4, 4, 3, 4, 2] * 2})
    first = (await client.post("/api/v1/career/recommendations/generate")).json()
    second = (await client.post("/api/v1/career/recommendations/generate")).json()
    assert [r["major"] for r in first] == [r["major"] for r in second]
    assert [r["fit_score"] for r in first] == [r["fit_score"] for r in second]


async def test_recommendation_without_grades_flags_missing_data(client):
    await _register(client, "career_nogrades@ex.com")
    recs = (await client.post("/api/v1/career/recommendations/generate")).json()
    assert len(recs) == 3
    # No grades -> rationale must admit there is no supporting data.
    assert any("belum ada nilai" in r["rationale"].lower() for r in recs)


async def test_roadmap_is_major_specific(client):
    await _register(client, "career_roadmap_major@ex.com")
    for subject, grade in [("Biologi", 95), ("Kimia", 92), ("Matematika", 80)]:
        await client.post("/api/v1/career/grades", json={"subject": subject, "grade": grade})
    await client.post("/api/v1/career/personality", json={"answers": [5, 4, 4, 5, 2] * 3})
    recs = (await client.post("/api/v1/career/recommendations/generate")).json()
    top_major = recs[0]["major"]
    await client.post("/api/v1/career/recommendations/submit")
    await client.post("/api/v1/career/recommendations/approve")
    milestones = (await client.get("/api/v1/career/roadmap")).json()
    assert len(milestones) == 3
    # Milestones must reference the chosen major's subjects/skills, not generic text.
    blob = " ".join(m["description"] + " ".join(m["tasks"]) for m in milestones)
    assert top_major in blob or "Kimia" in blob or "Biologi" in blob
    # Progress starts at a real value (0), not a fabricated 45.
    assert milestones[1]["progress_percent"] == 0
    assert milestones[2]["progress_percent"] == 0


async def test_recommendations_approved_cannot_be_regenerated(client):
    await _register(client, "career_locked@ex.com")
    await client.post("/api/v1/career/grades", json={"subject": "Fisika", "grade": 90})
    await client.post("/api/v1/career/recommendations/generate")
    await client.post("/api/v1/career/recommendations/submit")
    await client.post("/api/v1/career/recommendations/approve")
    again = await client.post("/api/v1/career/recommendations/generate")
    assert again.status_code == 409


async def test_resources_can_be_filtered_by_major(client):
    await _register(client, "career_res@ex.com")
    ordered = await client.get("/api/v1/career/resources?major=Ilmu Komputer")
    assert ordered.status_code == 200
    # Major-tagged resources float to the top without hiding the catalog.
    assert len(ordered.json()) >= 6


async def test_consultation_rejects_unknown_counselor(client):
    await _register(client, "career_bad_bk@ex.com")
    r = await client.post(
        "/api/v1/career/consultations",
        json={"counselor": "Dumbledore", "topic": "sihir"},
    )
    assert r.status_code == 409


async def test_assistant_personalises_jurusan_with_data(client):
    await _register(client, "career_chat_data@ex.com")
    await client.post("/api/v1/career/grades", json={"subject": "Fisika", "grade": 92})
    await client.post("/api/v1/career/personality", json={"answers": [4, 4, 3, 4, 2] * 2})
    await client.post("/api/v1/career/recommendations/generate")
    r = await client.post("/api/v1/career/assistant", json={"message": "rekomendasi jurusan saya?"})
    assert r.status_code == 200
    # Should reference an actual recommended major, not generic boilerplate.
    assert "Teknik" in r.json()["answer"] or "Komputer" in r.json()["answer"]
