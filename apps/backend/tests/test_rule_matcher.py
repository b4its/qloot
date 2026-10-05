"""Unit tests for the rule-based and fuzzy-matching knowledge engine."""

from __future__ import annotations

from app.ai.rule_matcher import (
    RuleBasedMatcher,
    extract_tokens,
    fuzzy_word_match,
    normalize_text,
)


def test_normalize_and_extract_tokens():
    raw = "Halo, apakah ada info SNBP 2026? & apa bedanya?!"
    norm = normalize_text(raw)
    assert "halo" in norm
    assert "snbp" in norm
    assert "?" not in norm

    tokens = extract_tokens(raw)
    assert "halo" in tokens
    assert "snbp" in tokens
    assert "bedanya" in tokens


def test_fuzzy_word_match():
    # Exact matches
    assert fuzzy_word_match("snbp", "snbp")
    assert fuzzy_word_match("dokter", "dokter")

    # Typos / spelling variations
    assert fuzzy_word_match("snbptn", "snbp")
    assert fuzzy_word_match("kedokterann", "kedokteran")
    assert fuzzy_word_match("informatikaa", "informatika")
    assert fuzzy_word_match("beasisswa", "beasiswa")

    # Mismatches
    assert not fuzzy_word_match("kucing", "kedokteran")
    assert not fuzzy_word_match("komputer", "kedokteran")


def test_matcher_exact_and_fuzzy_admissions():
    matcher = RuleBasedMatcher(assistant_name="Asisten Qlu")

    # SNBP vs SNBT
    res = matcher.match("Bedanya SNBP dan SNBT apa ya?")
    assert res is not None
    assert res["rule_id"] == "snbp_vs_snbt"
    assert "Perbedaan Utama SNBP vs SNBT" in res["answer"]
    assert res["confidence_bp"] >= 9000

    # SNBP with typo
    res_snbp = matcher.match("syarat jalur snbptn itu apa?")
    assert res_snbp is not None
    assert "SNBP" in res_snbp["answer"]

    # SNBT / UTBK
    res_snbt = matcher.match("materi utbk dan tes snbt apa saja?")
    assert res_snbt is not None
    assert "UTBK" in res_snbt["answer"]
    assert "TPS" in res_snbt["answer"]


def test_matcher_majors_and_campuses():
    matcher = RuleBasedMatcher(assistant_name="Asisten Qlu")

    # Computer Science
    res_cs = matcher.match("prospek kerja lulusan ilmu komputer dan teknik informatika")
    assert res_cs is not None
    assert "Software Engineer" in res_cs["answer"]

    # Medicine
    res_med = matcher.match("bagaimana kuliah kedokterann dan prospek dokter?")
    assert res_med is not None
    assert "Pendidikan Dokter" in res_med["answer"]

    # Campus recommendations
    res_campus = matcher.match("rekomendasi kampus teknik dan ptn terbaik di indonesia")
    assert res_campus is not None
    assert "ITB" in res_campus["answer"]


def test_matcher_scholarships_and_tips():
    matcher = RuleBasedMatcher(assistant_name="Asisten Qlu")

    # KIP Kuliah
    res_kip = matcher.match("bagaimana cara mendaftar beasisswa kip kuliah?")
    assert res_kip is not None
    assert "KIP Kuliah" in res_kip["answer"]

    # Study tips
    res_tips = matcher.match("tips belajar utbk dan manajemen waktu")
    assert res_tips is not None
    assert "Pomodoro" in res_tips["answer"]


def test_matcher_identity_and_fallback():
    matcher = RuleBasedMatcher(assistant_name="Asisten Qlu")

    # Identity
    res_id = matcher.match("siapa kamu sebenarnya?")
    assert res_id is not None
    assert "Asisten Qlu" in res_id["answer"]

    # Greeting
    res_greet = matcher.match("halo selamat pagi qlo")
    assert res_greet is not None
    assert "Halo" in res_greet["answer"]

    # Fallback guide when query is unrelated
    fallback = matcher.fallback_guide()
    assert "Asisten Qlu" in fallback["answer"]
    assert "Jalur Masuk PTN" in fallback["answer"]


def test_matcher_qlu_identity_and_greeting():
    matcher = RuleBasedMatcher(assistant_name="Asisten Qlu")
    res_id = matcher.match("siapa kamu sebenarnya?")
    assert res_id is not None
    assert "Asisten Qlu" in res_id["answer"]

    res_greet = matcher.match("halo selamat pagi qlo")
    assert res_greet is not None
    assert "Asisten Qlu" in res_greet["answer"]
