"""Metrics emission tests (AUTH-07).

The declared metrics were a mix of emitted and dead surface: several names in
``core/metrics.py`` had a HELP string but no code path ever incremented them.
These tests assert the counters are actually written by real flows and that no
declared metric is left without a writer.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role)


def _metric_names() -> set[str]:
    from app.core import metrics

    return set(metrics._HELP)  # noqa: SLF001 - intentionally inspecting the registry


async def test_metrics_endpoint_renders_prometheus_text(client):
    resp = await client.get("/api/v1/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


async def test_login_emits_auth_counters(client):
    await _register(client, "metrics_login@ex.com", "student")
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login",
        json={"email": "metrics_login@ex.com", "password": "Password123!"},
    )
    body = (await client.get("/api/v1/metrics")).text
    assert "auth_logins_total" in body


async def test_failed_login_emits_failure_counter(client):
    await _register(client, "metrics_fail@ex.com", "student")
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login",
        json={"email": "metrics_fail@ex.com", "password": "nope"},
    )
    body = (await client.get("/api/v1/metrics")).text
    assert "auth_login_failures_total" in body


async def test_grading_job_emits_ai_jobs_counter(client):
    """A real (mock) grading call must increment ``ai_jobs_total``."""
    await _register(client, "metrics_teacher@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "Metrics Exam"})
    exam_id = exam.json()["id"]
    question = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Explain something?", "correct_answer": "a", "position": 0, "qtype": "essay"},
    )
    question_id = question.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "metrics_student@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{question_id}",
        json={"answer_text": "some answer"},
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    grade = await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})
    assert grade.status_code == 200, grade.text

    body = (await client.get("/api/v1/metrics")).text
    assert "ai_jobs_total" in body


def test_no_declared_metric_is_dead():
    """Every HELP-declared metric must be referenced by at least one writer.

    Guards against the dead-surface pattern (a metric that dashboards expect
    but nothing ever increments).
    """
    import pathlib
    import re

    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    source = "\n".join(
        p.read_text(encoding="utf-8") for p in app_dir.rglob("*.py") if p.name != "metrics.py"
    )
    for name in sorted(_metric_names()):
        # A writer is either a literal name or a metrics.* call with the name.
        assert re.search(rf'"{name}"', source), f"declared metric {name!r} has no writer"


def test_histogram_renders_real_buckets():
    """AUTH-08: histograms expose cumulative ``_bucket`` lines, not just
    ``_count``/``_sum`` as the old summary rendering did."""
    from app.core import metrics

    metrics.observe("hist_test_seconds", 0.003)
    metrics.observe("hist_test_seconds", 0.3)
    metrics.observe("hist_test_seconds", 100.0)
    body = metrics.render()
    assert "# TYPE hist_test_seconds histogram" in body
    assert 'hist_test_seconds_bucket{le="0.005"} 1' in body
    assert 'hist_test_seconds_bucket{le="+Inf"} 3' in body
    assert "hist_test_seconds_count 3" in body
    # Cumulative monotonicity.
    buckets = [
        int(line.rsplit(" ", 1)[1])
        for line in body.splitlines()
        if line.startswith("hist_test_seconds_bucket")
    ]
    assert buckets == sorted(buckets)


def test_histogram_with_labels_keeps_labels_on_buckets():
    from app.core import metrics

    metrics.observe("labelled_latency_seconds", 0.2, method="GET")
    body = metrics.render()
    assert 'labelled_latency_seconds_bucket{method="GET",le="0.25"} 1' in body


def test_exposition_parses_as_prometheus_text():
    """The whole exposition must match the Prometheus text-format grammar.

    Implemented as a small structural validator (no dependency on
    ``prometheus_client`` being installed) so the gate holds offline.
    """
    import re

    from app.core import metrics

    metrics.incr("parse_test_total")
    metrics.observe("parse_test_seconds", 0.05)
    body = metrics.render()

    sample_re = re.compile(
        r'^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[a-zA-Z_][a-zA-Z0-9_]*="[^"]*"'
        r'(,[a-zA-Z_][a-zA-Z0-9_]*="[^"]*")*\})? -?[0-9.eE+]+$'
    )
    for line in body.splitlines():
        if line.startswith("#"):
            assert line.startswith(("# HELP ", "# TYPE ")), f"bad comment: {line}"
            continue
        assert sample_re.match(line), f"line is not valid Prometheus exposition: {line!r}"
