"""Unit tests for the deterministic MockProvider simulation.

These lock in the offline "AI" behaviour: reproducible question generation,
explainable grading (keyword/negation/length), ranked summarisation, and
grounded Q&A that reports when it cannot answer.
"""

from __future__ import annotations

import pytest

from app.ai.provider import (
    GenerationContext,
    GradeItem,
    GradingContext,
    MockProvider,
    QAContext,
    SummaryContext,
)

MATERIAL = (
    "Fotosintesis adalah proses tumbuhan mengubah cahaya matahari menjadi energi kimia. "
    "Proses ini terjadi di kloroplas dan membutuhkan air serta karbon dioksida. "
    "Hasil fotosintesis adalah glukosa dan oksigen yang dilepaskan ke udara. "
    "Klorofil berperan menyerap energi cahaya untuk reaksi terang."
)


@pytest.mark.asyncio
async def test_generate_questions_is_deterministic_and_non_empty():
    provider = MockProvider()
    ctx = GenerationContext(text=MATERIAL, count=3, title="Biologi")
    first = await provider.generate_questions(ctx)
    second = await provider.generate_questions(ctx)
    assert first == second  # fully deterministic
    assert len(first.questions) == 3
    for q in first.questions:
        assert q.prompt
        assert q.correct_answer
        assert "Biologi" in q.prompt


@pytest.mark.asyncio
async def test_generate_questions_varies_form_not_just_echo():
    provider = MockProvider()
    ctx = GenerationContext(text=MATERIAL, count=3, title="Biologi")
    result = await provider.generate_questions(ctx)
    prompts = [q.prompt for q in result.questions]
    # Not the same template repeated verbatim.
    assert len(set(prompts)) == len(prompts)


@pytest.mark.asyncio
async def test_generate_questions_handles_empty_text_gracefully():
    provider = MockProvider()
    result = await provider.generate_questions(GenerationContext(text="", count=2))
    assert len(result.questions) == 2
    # Should be clearly labelled placeholders, not fake confident answers.
    assert all("belum" in q.correct_answer.lower() for q in result.questions)


@pytest.mark.asyncio
async def test_generate_questions_caps_count():
    provider = MockProvider()
    result = await provider.generate_questions(GenerationContext(text=MATERIAL, count=999))
    # Never exceeds the configured maximum.
    assert len(result.questions) <= 20


@pytest.mark.asyncio
async def test_grade_rewards_relevant_answer_over_irrelevant():
    provider = MockProvider()
    ctx = GradingContext(
        items=[
            GradeItem(
                question="Apa itu fotosintesis?",
                correct_answer="Fotosintesis mengubah cahaya matahari menjadi energi kimia di kloroplas.",
                student_answer="Fotosintesis mengubah cahaya matahari menjadi energi kimia.",
            ),
            GradeItem(
                question="Apa itu fotosintesis?",
                correct_answer="Fotosintesis mengubah cahaya matahari menjadi energi kimia di kloroplas.",
                student_answer="Saya tidak tahu sama sekali tentang topik ini.",
            ),
        ]
    )
    result = await provider.grade(ctx)
    assert result.items[0].score_bp > result.items[1].score_bp
    assert result.items[0].similarity_bp > result.items[1].similarity_bp


@pytest.mark.asyncio
async def test_grade_empty_answer_scores_zero():
    provider = MockProvider()
    result = await provider.grade(
        GradingContext(items=[GradeItem(question="q", correct_answer="kloroplas", student_answer="")])
    )
    assert result.items[0].score_bp == 0


@pytest.mark.asyncio
async def test_grade_missing_reference_is_neutral_not_length_rewarded():
    provider = MockProvider()
    long_answer = "kata " * 200
    result = await provider.grade(
        GradingContext(items=[GradeItem(question="q", correct_answer="", student_answer=long_answer)])
    )
    # No key => neutral, and NOT boosted just for being long.
    assert result.items[0].score_bp == 5000


@pytest.mark.asyncio
async def test_grade_names_missing_key_points_in_feedback():
    provider = MockProvider()
    result = await provider.grade(
        GradingContext(
            items=[
                GradeItem(
                    question="q",
                    correct_answer="fotosintesis menghasilkan glukosa dan oksigen di kloroplas",
                    student_answer="fotosintesis menghasilkan glukosa",
                )
            ]
        )
    )
    fb = result.items[0].feedback.lower()
    assert "oksigen" in fb or "kloroplas" in fb


@pytest.mark.asyncio
async def test_grade_penalises_negation_mismatch():
    provider = MockProvider()
    ref = "Reaksi ini menghasilkan energi."
    correct = "Reaksi ini menghasilkan energi."
    negated = "Reaksi ini tidak menghasilkan energi."
    items = [
        GradeItem(question="q", correct_answer=ref, student_answer=correct),
        GradeItem(question="q", correct_answer=ref, student_answer=negated),
    ]
    result = await provider.grade(GradingContext(items=items))
    assert result.items[0].score_bp > result.items[1].score_bp


@pytest.mark.asyncio
async def test_summarize_respects_word_budget_and_is_deterministic():
    provider = MockProvider()
    ctx = SummaryContext(text=MATERIAL, max_words=30)
    first = await provider.summarize(ctx)
    second = await provider.summarize(ctx)
    assert first == second
    assert len(first.summary.split()) <= 30
    assert first.key_points


@pytest.mark.asyncio
async def test_summarize_empty_returns_placeholder():
    provider = MockProvider()
    result = await provider.summarize(SummaryContext(text=""))
    assert result.summary
    assert result.key_points == []


@pytest.mark.asyncio
async def test_answer_grounded_in_material():
    provider = MockProvider()
    result = await provider.answer(QAContext(text=MATERIAL, question="Di mana fotosintesis terjadi?"))
    assert "kloroplas" in result.answer.lower()
    assert result.confidence_bp > 5000


@pytest.mark.asyncio
async def test_answer_reports_when_material_does_not_cover_topic():
    provider = MockProvider()
    result = await provider.answer(
        QAContext(text=MATERIAL, question="Bagaimana cara kerja mesin diesel turbo?")
    )
    assert result.confidence_bp <= 2500


@pytest.mark.asyncio
async def test_provider_is_deterministic_across_instances():
    a = MockProvider()
    b = MockProvider()
    ctx = GradingContext(items=[GradeItem(question="q", correct_answer="glukosa oksigen", student_answer="glukosa")])
    assert await a.grade(ctx) == await b.grade(ctx)
