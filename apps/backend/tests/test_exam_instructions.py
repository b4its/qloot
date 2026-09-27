"""Exam instructions round-trip (create → read → update).

``ExamUpdate`` accepted ``instructions`` but ``ExamOut`` never returned it, so the
field was effectively write-only. This guards the read path so the editor can
load and display the saved instructions.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _teacher(client, email="exam_instr@ex.com"):
    from tests.helpers import register_actor

    return await register_actor(client, email, "teacher", full_name="Exam Teacher")


async def test_instructions_are_returned_and_updatable(client):
    await _teacher(client)

    # Create an exam with instructions.
    created = await client.post(
        "/api/v1/exams",
        json={
            "title": "Ujian Instruksi",
            "duration_minutes": 30,
            "instructions": "Baca setiap soal dengan teliti.",
        },
    )
    assert created.status_code == 201, created.text
    exam_id = created.json()["id"]
    # The read path must surface the field.
    assert created.json()["instructions"] == "Baca setiap soal dengan teliti."

    # A fresh GET also carries it.
    got = await client.get(f"/api/v1/exams/{exam_id}")
    assert got.status_code == 200, got.text
    assert got.json()["instructions"] == "Baca setiap soal dengan teliti."

    # Update the instructions.
    patched = await client.patch(
        f"/api/v1/exams/{exam_id}",
        json={"instructions": "Waktu 30 menit. Dilarang menyontek."},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["instructions"] == "Waktu 30 menit. Dilarang menyontek."
