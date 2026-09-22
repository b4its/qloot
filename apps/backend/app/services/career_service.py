"""Career guidance service (simulated).

Implements, deterministically and offline:
  - academic dashboard aggregation (avg, strong/weak subjects, trend, insights)
  - Big Five personality scoring from a Likert simulation
  - AI major recommendation engine (academic + personality fit)
  - roadmap milestone generation + progress tracking (human-in-the-loop)
  - BK consultation booking CRUD
  - resource library catalog
  - rule-based assistant chat
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.career import (
    AcademicGrade,
    CareerRecommendation,
    Consultation,
    PersonalityResult,
    ResourceItem,
    RoadmapMilestone,
)
from app.models.identity import User
from app.services.social_service import NotificationService

log = get_logger("career")

# --- Big Five dimensions ---------------------------------------------------
TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]

# --- Major catalog: which subjects & traits matter for each major ----------
MAJOR_CATALOG: list[dict] = [
    {
        "major": "Teknik Elektro",
        "subjects": {"Fisika": 0.4, "Matematika": 0.4, "Kimia": 0.1, "B. Inggris": 0.1},
        "traits": {"conscientiousness": 0.5, "openness": 0.3, "neuroticism": -0.2},
        "universities": ["ITB", "ITS", "Universitas Indonesia", "UGM"],
        "admission_paths": ["SNBP (nilai rapor)", "SNBT (UTBK)", "Jalur Mandiri"],
        "skills": ["Matematika teknik", "Elektronika dasar", "Pemrograman dasar"],
        "careers": ["Teknisi listrik", "Engineer energi", "IoT specialist"],
    },
    {
        "major": "Ilmu Komputer",
        "subjects": {"Matematika": 0.45, "Fisika": 0.15, "B. Inggris": 0.2, "B. Indonesia": 0.2},
        "traits": {"conscientiousness": 0.45, "openness": 0.4, "extraversion": -0.1},
        "universities": ["ITB", "Universitas Indonesia", "BINUS", "ITS"],
        "admission_paths": ["SNBP (nilai rapor)", "SNBT (UTBK)", "Jalur Mandiri"],
        "skills": ["Algoritma", "Python/JavaScript", "Basis data"],
        "careers": ["Software Engineer", "Data Scientist", "AI Engineer"],
    },
    {
        "major": "Teknik Industri",
        "subjects": {"Matematika": 0.4, "Fisika": 0.2, "B. Inggris": 0.2, "B. Indonesia": 0.2},
        "traits": {"conscientiousness": 0.4, "agreeableness": 0.3, "extraversion": 0.2},
        "universities": ["ITB", "ITS", "Universitas Indonesia"],
        "admission_paths": ["SNBP (nilai rapor)", "SNBT (UTBK)"],
        "skills": ["Statistika", "Manajemen proses", "Optimisasi"],
        "careers": ["Industrial Engineer", "Supply Chain Analyst", "Operations Manager"],
    },
    {
        "major": "Kedokteran",
        "subjects": {"Biologi": 0.4, "Kimia": 0.35, "Matematika": 0.15, "B. Inggris": 0.1},
        "traits": {"conscientiousness": 0.5, "agreeableness": 0.35, "neuroticism": -0.15},
        "universities": ["Universitas Indonesia", "UGM", "Universitas Airlangga"],
        "admission_paths": ["SNBP (nilai rapor)", "SNBT (UTBK)", "Jalur Mandiri"],
        "skills": ["Biologi molekuler", "Anatomi", "Komunikasi klinis"],
        "careers": ["Dokter umum", "Spesialis", "Peneliti medis"],
    },
    {
        "major": "Akuntansi",
        "subjects": {"Matematika": 0.4, "B. Indonesia": 0.3, "B. Inggris": 0.3},
        "traits": {"conscientiousness": 0.5, "agreeableness": 0.2, "extraversion": 0.1},
        "universities": ["Universitas Indonesia", "UGM", "Universitas Brawijaya"],
        "admission_paths": ["SNBP (nilai rapor)", "SNBT (UTBK)"],
        "skills": ["Akuntansi keuangan", "Audit", "Perpajakan"],
        "careers": ["Akuntan publik", "Auditor", "Financial Analyst"],
    },
    {
        "major": "Psikologi",
        "subjects": {"Biologi": 0.3, "B. Indonesia": 0.35, "B. Inggris": 0.35},
        "traits": {"agreeableness": 0.4, "openness": 0.35, "extraversion": 0.2},
        "universities": ["Universitas Indonesia", "UGM", "Universitas Padjadjaran"],
        "admission_paths": ["SNBP (nilai rapor)", "SNBT (UTBK)"],
        "skills": ["Metodologi riset", "Statistika sosial", "Wawancara"],
        "careers": ["Psikolog klinis", "HR Specialist", "Researcher"],
    },
]

# --- Resource library (seed data) ------------------------------------------
RESOURCE_CATALOG: list[tuple[str, str, str, str, str, bool, list[str]]] = [
    (
        "course-robotika",
        "course",
        "Dasar-Dasar Robotika",
        "Pengenalan robotika untuk pemula.",
        "Coursera",
        True,
        ["Teknik Elektro"],
    ),
    (
        "course-python",
        "course",
        "Pengantar Pemrograman Python",
        "Dasar coding dengan Python.",
        "Dicoding",
        True,
        ["Ilmu Komputer"],
    ),
    (
        "course-stoikiometri",
        "course",
        "Kimia Dasar: Stoikiometri",
        "Latihan soal stoikiometri.",
        "Zenius",
        False,
        ["Kedokteran"],
    ),
    (
        "course-matdis",
        "course",
        "Matematika Diskrit",
        "Logika matematika & struktur diskrit.",
        "Ruangguru",
        True,
        ["Ilmu Komputer"],
    ),
    (
        "course-fisika-terapan",
        "course",
        "Fisika Terapan untuk Teknik",
        "Mekanika dan elektromagnetika terapan.",
        "Udemy",
        False,
        ["Teknik Elektro"],
    ),
    (
        "course-toefl",
        "course",
        "Bahasa Inggris Akademik",
        "Academic English & technical writing.",
        "British Council",
        True,
        [],
    ),
    (
        "course-statistika",
        "course",
        "Statistika Dasar untuk Riset",
        "Analisis statistik untuk penelitian.",
        "Coursera",
        True,
        ["Psikologi"],
    ),
    (
        "course-jaringan",
        "course",
        "Jaringan Komputer Dasar",
        "TCP/IP, routing, keamanan jaringan.",
        "Cisco Academy",
        True,
        ["Ilmu Komputer"],
    ),
    (
        "exkul-robotika",
        "extracurricular",
        "Klub Robotika",
        "Kompetisi robotika tingkat kota.",
        "Sekolah",
        True,
        ["Teknik Elektro"],
    ),
    (
        "exkul-olimpiade",
        "extracurricular",
        "Olimpiade Fisika",
        "Persiapan olimpiade fisika.",
        "Sekolah",
        True,
        ["Teknik Elektro"],
    ),
    (
        "exkul-coding",
        "extracurricular",
        "Komunitas Coding",
        "Belajar pemrograman peer-to-peer.",
        "Sekolah",
        True,
        ["Ilmu Komputer"],
    ),
    (
        "exkul-kir",
        "extracurricular",
        "Kelompok Ilmiah Remaja",
        "Riset dan karya tulis ilmiah.",
        "Sekolah",
        True,
        [],
    ),
    (
        "exkul-english",
        "extracurricular",
        "English Club",
        "Debat dan pidato bahasa Inggris.",
        "Sekolah",
        True,
        [],
    ),
    (
        "exkul-jurnalistik",
        "extracurricular",
        "Jurnalistik Sekolah",
        "Menulis artikel dan liputan.",
        "Sekolah",
        True,
        ["Psikologi"],
    ),
    (
        "mat-stoikiometri",
        "material",
        "Modul Stoikiometri",
        "30 soal + pembahasan.",
        "QLoot",
        True,
        ["Kedokteran"],
    ),
    (
        "mat-fisika",
        "material",
        "Bank Soal Fisika Mekanika",
        "Soal mekanika dasar.",
        "QLoot",
        True,
        ["Teknik Elektro"],
    ),
    ("mat-utbk", "material", "Kumpulan Soal UTBK", "Bank soal UTBK 5 tahun.", "QLoot", True, []),
    (
        "mat-matriks",
        "material",
        "Modul Matriks & Vektor",
        "Operasi matriks dan vektor.",
        "QLoot",
        True,
        ["Ilmu Komputer"],
    ),
    (
        "mat-esai",
        "material",
        "Panduan Esai & Portofolio",
        "Menulis esai dan portofolio.",
        "QLoot",
        True,
        [],
    ),
]

CONSULTANTS = [
    ("Bu Ratna Wijaya", "Guru BK - Kelas X-XI", "Pemilihan jurusan dan minat bakat"),
    ("Pak Aditya Nugraha", "Guru BK - Kelas XII", "Akademik dan seleksi perguruan tinggi"),
]


def _clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    return int(max(lo, min(hi, round(value))))


def _term_sort_key(term: str) -> tuple[int, int]:
    """Parse a term like '2025/2026-genap' into a sortable (year, half) key.

    'ganjil' (odd semester) sorts before 'genap' (even). Unknown formats fall
    back to (0, 0) so they sort first and are treated as the oldest data.
    """
    m = re.match(r"(\d{4})", term or "")
    year = int(m.group(1)) if m else 0
    half = 1 if "genap" in (term or "").lower() else 0
    return (year, half)


def _latest_per_subject(grades: list[AcademicGrade]) -> dict[str, int]:
    """Collapse rows to the most recent grade per subject (deterministic).

    Rows are ordered by (term, subject) so the *latest* term wins regardless
    of DB row order — the same input always yields the same output.
    """
    ordered = sorted(grades, key=lambda g: (_term_sort_key(g.term), g.subject))
    latest: dict[str, int] = {}
    for g in ordered:
        latest[g.subject] = g.grade
    return latest


# Which academic 'rumpun' (cluster) a strong subject points to; drives the
# personalised "potential" insight instead of a hardcoded teknik/sains string.
_SUBJECT_CLUSTER: dict[str, str] = {
    "Fisika": "teknik & sains",
    "Matematika": "teknik & sains",
    "Kimia": "sains & kesehatan",
    "Biologi": "sains & kesehatan",
    "B. Indonesia": "sosial & humaniora",
    "B. Inggris": "bahasa & komunikasi",
    "Sejarah": "sosial & humaniora",
    "Ekonomi": "bisnis & ekonomi",
    "Sosiologi": "sosial & humaniora",
    "Geografi": "sains & sosial",
}


class CareerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- grades ------------------------------------------------------------
    async def list_grades(
        self, user_id: uuid.UUID, *, limit: int = 1000, offset: int = 0
    ) -> list[AcademicGrade]:
        stmt = (
            select(AcademicGrade)
            .where(AcademicGrade.user_id == user_id)
            .order_by(AcademicGrade.subject)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def upsert_grade(self, user_id: uuid.UUID, subject: str, grade: int, term: str):
        existing = (
            await self.session.execute(
                select(AcademicGrade).where(
                    AcademicGrade.user_id == user_id,
                    AcademicGrade.subject == subject,
                    AcademicGrade.term == term,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = AcademicGrade(user_id=user_id, subject=subject, grade=grade, term=term)
            self.session.add(existing)
        else:
            existing.grade = grade
        await self.session.flush()
        return existing

    async def delete_grade(self, user_id: uuid.UUID, grade_id: uuid.UUID) -> None:
        """Remove one of the caller's academic grades."""
        grade = (
            await self.session.execute(
                select(AcademicGrade).where(
                    AcademicGrade.id == grade_id, AcademicGrade.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if grade is None:
            raise NotFoundError("Grade not found")
        await self.session.delete(grade)
        await self.session.flush()

    async def dashboard(self, user: User) -> dict:
        grades = await self.list_grades(user.id)
        if not grades:
            return {
                "average": 0,
                "strong_subject": None,
                "weak_subject": None,
                "subjects": [],
                "trend": [],
                "radar": [],
                "insights": [],
            }

        latest = _latest_per_subject(grades)
        subjects = [{"subject": s, "grade": g} for s, g in sorted(latest.items())]
        avg = _clamp(sum(latest.values()) / len(latest))

        ordered_subjects = sorted(latest.items(), key=lambda kv: kv[1])
        weak_subject, weak_grade = ordered_subjects[0]
        strong_subject, strong_grade = ordered_subjects[-1]

        trend = self._trend_from_grades(grades)
        radar = self._radar_from_grades(grades)

        # Insights derived from the actual data (no hardcoded claims).
        insights: list[dict] = []
        if len(latest) == 1:
            insights.append(
                {
                    "kind": "potential",
                    "title": f"{strong_subject} menjadi titik kuat",
                    "detail": (
                        f"Nilai {strong_subject} ({strong_grade}). Tambahkan nilai mata "
                        "pelajaran lain untuk analisis yang lebih kaya."
                    ),
                }
            )
        else:
            insights.append(
                {
                    "kind": "consistency",
                    "title": f"{strong_subject} konsisten kuat",
                    "detail": f"Nilai {strong_subject} tertinggi ({strong_grade}). Pertahankan.",
                }
            )
            insights.append(
                {
                    "kind": "attention",
                    "title": f"{weak_subject} perlu perhatian",
                    "detail": f"Nilai {weak_subject} terendah ({weak_grade}). Fokus penguatan.",
                }
            )
            cluster = _SUBJECT_CLUSTER.get(strong_subject, "yang sesuai minatmu")
            insights.append(
                {
                    "kind": "potential",
                    "title": "Proyeksi rumpun studi",
                    "detail": (
                        f"Kekuatan pada {strong_subject} mengarah ke rumpun {cluster}. "
                        "Lengkapi profil kepribadian untuk rekomendasi jurusan personal."
                    ),
                }
            )

        return {
            "average": avg,
            "strong_subject": strong_subject,
            "weak_subject": weak_subject,
            "subjects": subjects,
            "trend": trend,
            "radar": radar,
            "insights": insights,
        }

    def _trend_from_grades(self, grades: list[AcademicGrade]) -> list[dict]:
        """Average grade per term, ordered chronologically (deterministic).

        The trend is derived from real graded terms rather than a fabricated
        rising line, so it reflects the student's actual history.
        """
        by_term: dict[str, list[int]] = {}
        for g in grades:
            by_term.setdefault(g.term, []).append(g.grade)
        ordered = sorted(by_term.items(), key=lambda kv: _term_sort_key(kv[0]))
        return [{"month": term, "value": _clamp(sum(vals) / len(vals))} for term, vals in ordered]

    def _radar_from_grades(self, grades: list[AcademicGrade]) -> list[dict]:
        latest = _latest_per_subject(grades)

        def avg_of(*subjects: str) -> float | None:
            present = [latest[s] for s in subjects if s in latest]
            return sum(present) / len(present) if present else None

        # Only use real grades; fall back to a neutral 50 (not a flattering 75)
        # when a dimension has no supporting data. Note: test for ``None``
        # explicitly — a genuine grade of 0 must not be coerced to 50 by ``or``.
        def dim(*subjects: str) -> float:
            value = avg_of(*subjects)
            return 50.0 if value is None else value

        dims: dict[str, float] = {
            "Sains": dim("Fisika", "Kimia", "Biologi"),
            "Teknik": dim("Matematika", "Fisika"),
            "Bahasa": dim("B. Inggris", "B. Indonesia"),
            "Sosial": dim("Sosiologi", "Sejarah", "Geografi", "B. Indonesia"),
            "Bisnis": dim("Ekonomi", "Matematika"),
            "Seni": dim("Seni Budaya", "Prakarya"),
        }
        return [{"dimension": k, "value": _clamp(v)} for k, v in dims.items()]

    # --- personality -------------------------------------------------------
    async def latest_personality(self, user_id: uuid.UUID) -> PersonalityResult | None:
        stmt = (
            select(PersonalityResult)
            .where(PersonalityResult.user_id == user_id)
            .order_by(PersonalityResult.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def score_personality(self, user: User, answers: list[int]) -> PersonalityResult:
        """Score a Big Five simulation from 10-50 Likert answers (1-5).

        Deterministic. Answers map to a fixed, balanced item bank: each item is
        keyed to a trait and may be reverse-scored (a *negative* key means a
        high Likert response indicates *less* of the trait). This mirrors how a
        real inventory is scored, instead of assigning traits purely by
        position. Items are distributed evenly across the five traits.
        """
        if len(answers) < 5:
            raise ConflictError("At least 5 answers are required")
        n = len(answers)
        # Even round-robin distribution (spreads any remainder deterministically
        # so traits are computed from near-equal sample sizes).
        buckets: dict[str, list[int]] = {t: [] for t in TRAITS}
        # Reverse-keyed positions: every 3rd item within a trait is inverted,
        # giving each trait a mix of positively- and negatively-keyed items.
        counts: dict[str, int] = dict.fromkeys(TRAITS, 0)
        for i, ans in enumerate(answers):
            trait = TRAITS[i % 5]
            value = max(1, min(5, int(ans)))
            if counts[trait] % 3 == 2:
                value = 6 - value  # reverse score
            buckets[trait].append(value)
            counts[trait] += 1

        def pct(vals: list[int]) -> int:
            if not vals:
                return 50
            avg = sum(vals) / len(vals)  # 1..5
            return _clamp((avg - 1) / 4 * 100)

        result = PersonalityResult(
            user_id=user.id,
            openness=pct(buckets["openness"]),
            conscientiousness=pct(buckets["conscientiousness"]),
            extraversion=pct(buckets["extraversion"]),
            agreeableness=pct(buckets["agreeableness"]),
            neuroticism=pct(buckets["neuroticism"]),
            answers={"raw": answers, "n": n},
        )
        # Summary mentions the dominant trait *and* emotional stability (the
        # inverse of neuroticism), so high-neuroticism profiles are surfaced.
        named = [
            ("Keterbukaan", result.openness),
            ("Kehati-hatian", result.conscientiousness),
            ("Ekstroversi", result.extraversion),
            ("Keramahan", result.agreeableness),
        ]
        top = max(named, key=lambda x: x[1])
        stability = 100 - result.neuroticism
        result.summary = (
            f"Profil menonjol pada {top[0]} ({top[1]}). "
            f"Stabilitas emosi {stability}/100. "
            "Cocok untuk bidang yang menuntut kombinasi tersebut."
        )
        self.session.add(result)
        await self.session.flush()
        log.info("personality_scored", user_id=str(user.id))
        return result

    # --- recommendations ---------------------------------------------------
    async def generate_recommendations(
        self, user: User, top_n: int = 3
    ) -> list[CareerRecommendation]:
        # Deterministic: use the latest grade per subject (never depend on the
        # incidental DB row order of multi-term duplicates).
        grades = _latest_per_subject(await self.list_grades(user.id))
        personality = await self.latest_personality(user.id)

        scored: list[tuple[float, dict, int, int, float]] = []
        for major in MAJOR_CATALOG:
            # Academic fit is computed only over *available* subjects, and we
            # track how much of the major's weighting we could actually cover
            # (coverage). Missing subjects neither inflate nor silently default
            # to a flattering 70.
            covered = 0.0
            total_weight = sum(major["subjects"].values()) or 1.0
            weighted = 0.0
            for subject, weight in major["subjects"].items():
                if subject in grades:
                    covered += weight
                    weighted += grades[subject] * weight
            coverage = covered / total_weight
            academic_score = weighted / covered if covered else 0.0

            personality_score = 60.0
            if personality is not None:
                pts = 0.0
                wsum = 0.0
                for trait, weight in major["traits"].items():
                    value = getattr(personality, trait, 50)
                    # Negative weight means "lower is better" (e.g. neuroticism).
                    contribution = value if weight >= 0 else (100 - value)
                    pts += contribution * abs(weight)
                    wsum += abs(weight)
                personality_score = pts / (wsum or 1)

            # Confidence scales the whole fit by how much data we had, so a
            # student with no grades cannot out-rank one with a full profile.
            confidence = 0.5 + 0.5 * coverage if personality is None else 0.6 + 0.4 * coverage
            fit = (academic_score * 0.6 + personality_score * 0.4) * confidence
            scored.append((fit, major, _clamp(academic_score), _clamp(personality_score), coverage))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Clear prior drafts and regenerate. Approved recommendation sets are
        # left intact so an activated roadmap is never silently desynced.
        prior = (
            (
                await self.session.execute(
                    select(CareerRecommendation).where(CareerRecommendation.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        if any(r.status == "approved" for r in prior):
            raise ConflictError(
                "Recommendations were already approved. Reset the roadmap before regenerating."
            )
        for row in prior:
            await self.session.delete(row)
        await self.session.flush()

        results: list[CareerRecommendation] = []
        for rank, (fit, major, academic_fit, personality_fit, coverage) in enumerate(
            scored[:top_n], start=1
        ):
            # Reference the concrete subjects that drove the score.
            subject_hits = [
                (s, grades[s])
                for s in sorted(major["subjects"], key=lambda s: major["subjects"][s], reverse=True)
                if s in grades
            ]
            if subject_hits:
                cause = ", ".join(f"{s} ({g})" for s, g in subject_hits[:2])
                rationale = (
                    f"Nilai kuat pada {cause} mendukung {major['major']}. "
                    f"Cakupan data {int(coverage * 100)}%."
                )
            else:
                rationale = (
                    f"Belum ada nilai pendukung untuk {major['major']}. "
                    "Masukkan nilai rapor agar rekomendasi lebih akurat."
                )

            rec = CareerRecommendation(
                user_id=user.id,
                major=major["major"],
                fit_score=_clamp(fit),
                academic_fit=academic_fit,
                personality_fit=personality_fit,
                rationale=rationale,
                universities=major["universities"],
                admission_paths=major["admission_paths"],
                skills=major["skills"],
                careers=major["careers"],
                rank=rank,
                status="draft",
            )
            self.session.add(rec)
            results.append(rec)
        await self.session.flush()
        log.info("career_recommendations_generated", user_id=str(user.id), n=len(results))
        return results

    async def list_recommendations(
        self, user_id: uuid.UUID, *, limit: int = 1000, offset: int = 0
    ) -> list[CareerRecommendation]:
        stmt = (
            select(CareerRecommendation)
            .where(CareerRecommendation.user_id == user_id)
            .order_by(CareerRecommendation.rank)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def submit_for_review(self, user: User) -> int:
        recs = await self.list_recommendations(user.id)
        if not recs:
            raise NotFoundError("No recommendations to submit")
        for r in recs:
            r.status = "in_review"
        await NotificationService(self.session).notify(
            user_id=user.id,
            kind="system",
            title="Analisis dikirim ke Guru BK",
            body="Rekomendasi jalur studi Anda menunggu persetujuan guru BK.",
        )
        await self.session.flush()
        return len(recs)

    async def pending_review(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[tuple[uuid.UUID, str, str, int]]:
        """Students whose recommendations await approval (for the counselor).

        Returns (user_id, full_name, top_major, recommendation_count) for every
        user with at least one ``in_review`` recommendation.
        """
        from app.models.identity import User

        stmt = (
            select(
                CareerRecommendation.user_id,
                User.full_name,
                func.count(CareerRecommendation.id).label("n"),
            )
            .join(User, User.id == CareerRecommendation.user_id)
            .where(CareerRecommendation.status == "in_review")
            .group_by(CareerRecommendation.user_id, User.full_name)
            .order_by(User.full_name)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()
        out: list[tuple[uuid.UUID, str, str, int]] = []
        for user_id, name, n in rows:
            top = (
                await self.session.execute(
                    select(CareerRecommendation.major)
                    .where(
                        CareerRecommendation.user_id == user_id,
                        CareerRecommendation.status == "in_review",
                    )
                    .order_by(CareerRecommendation.rank)
                    .limit(1)
                )
            ).scalar_one_or_none()
            out.append((user_id, name, top or "", int(n)))
        return out

    async def approve(self, user: User) -> int:
        return await self.approve_user(user.id)

    async def approve_user(self, user_id: uuid.UUID) -> int:
        """Approve a user's recommendations and activate their roadmap.

        Kept user-id-based (not caller-based) so a counselor can approve a
        student's plan; the caller-side RBAC lives in the router.
        """
        recs = await self.list_recommendations(user_id)
        if not recs:
            raise NotFoundError("No recommendations to approve")
        for r in recs:
            r.status = "approved"
        if not await self.list_milestones(user_id):
            await self._build_roadmap_by_id(user_id, recs[0].major)
        await NotificationService(self.session).notify(
            user_id=user_id,
            kind="system",
            title="Roadmap diaktifkan",
            body="Selamat! Roadmap jalur studi Anda telah disahkan.",
        )
        await self.session.flush()
        return len(recs)

    # --- roadmap -----------------------------------------------------------
    async def list_milestones(
        self, user_id: uuid.UUID, *, limit: int = 1000, offset: int = 0
    ) -> list[RoadmapMilestone]:
        stmt = (
            select(RoadmapMilestone)
            .where(RoadmapMilestone.user_id == user_id)
            .order_by(RoadmapMilestone.position)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _build_roadmap(self, user: User, major: str) -> list[RoadmapMilestone]:
        return await self._build_roadmap_by_id(user.id, major)

    async def _build_roadmap_by_id(self, user_id: uuid.UUID, major: str) -> list[RoadmapMilestone]:
        """Build a roadmap tailored to the chosen major's catalog entry.

        Subjects, skills and admission paths come from MAJOR_CATALOG, so a
        Kedokteran roadmap looks different from an Akuntansi one. Periods are
        concrete month offsets from "now". Progress starts at 0 (no fake 45%).
        """
        entry = next((m for m in MAJOR_CATALOG if m["major"] == major), None)
        subjects = list((entry or {}).get("subjects", {}).keys()) or ["mata pelajaran inti"]
        skills = list((entry or {}).get("skills", [])) or ["keterampilan dasar"]
        paths = list((entry or {}).get("admission_paths", [])) or ["SNBP (nilai rapor)"]

        now = datetime.now(UTC)
        specs = [
            (
                self._period_label(now, 0, 3),
                "Penguatan Fondasi Akademik",
                f"Perkuat {', '.join(subjects)} sebagai fondasi untuk {major}.",
                [f"Latihan soal {subjects[0]} 3x/minggu", "Review materi mingguan"],
                0,
                "in_progress",
            ),
            (
                self._period_label(now, 3, 8),
                "Eksplorasi Proyek & Kompetisi",
                f"Bangun portofolio {major} lewat proyek dan kompetisi.",
                [f"Kuasai: {skills[0]}"] + ([f"Latih: {skills[1]}"] if len(skills) > 1 else []),
                0,
                "not_started",
            ),
            (
                self._period_label(now, 8, 12),
                "Persiapan Seleksi Masuk PTN",
                f"Fokus pada jalur: {', '.join(paths)}.",
                ["Try out bulanan", "Simulasi UTBK/SNBT"],
                0,
                "not_started",
            ),
        ]
        created: list[RoadmapMilestone] = []
        for i, (period, title, desc, tasks, prog, status) in enumerate(specs):
            m = RoadmapMilestone(
                user_id=user_id,
                title=title,
                description=desc,
                period=period,
                position=i,
                progress_percent=prog,
                status=status,
                tasks=[t for t in tasks if t],
            )
            self.session.add(m)
            created.append(m)
        await self.session.flush()
        return created

    @staticmethod
    def _period_label(anchor: datetime, start_month: int, end_month: int) -> str:
        """Format a concrete 'Mon YYYY – Mon YYYY' range offset from an anchor."""

        def shown(offset: int) -> str:
            total = anchor.month - 1 + offset
            year = anchor.year + total // 12
            month = total % 12 + 1
            return datetime(year, month, 1).strftime("%b %Y")

        if start_month == 0:
            return f"Bulan ke-1 – {shown(end_month)}"
        return f"{shown(start_month)} – {shown(end_month)}"

    async def update_milestone(
        self, user_id: uuid.UUID, milestone_id: uuid.UUID, progress_percent: int
    ) -> RoadmapMilestone:
        m = await self.session.get(RoadmapMilestone, milestone_id)
        if m is None or m.user_id != user_id:
            raise NotFoundError("Milestone not found")
        m.progress_percent = _clamp(progress_percent)
        m.status = (
            "completed"
            if m.progress_percent >= 100
            else ("in_progress" if m.progress_percent > 0 else "not_started")
        )
        await self.session.flush()
        return m

    # --- consultations -----------------------------------------------------
    async def list_consultations(
        self, user_id: uuid.UUID, *, limit: int = 1000, offset: int = 0
    ) -> list[Consultation]:
        stmt = (
            select(Consultation)
            .where(Consultation.user_id == user_id)
            .order_by(Consultation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_consultation(
        self, user: User, *, counselor: str, topic: str, notes: str | None
    ) -> Consultation:
        valid = {n for n, _r, _f in CONSULTANTS}
        if counselor not in valid:
            raise ConflictError(f"Unknown counselor. Choose one of: {', '.join(sorted(valid))}")
        # Deterministic slot: first free weekday slot 3 days out, so repeat
        # bookings don't pile onto the exact same timestamp.
        slot = datetime.now(UTC) + timedelta(days=3)
        existing_today = len(
            [
                c
                for c in await self.list_consultations(user.id)
                if c.status == "pending" and c.counselor == counselor
            ]
        )
        scheduled = slot + timedelta(hours=existing_today)  # one-hour spacing
        c = Consultation(
            user_id=user.id,
            counselor=counselor,
            topic=topic,
            scheduled_at=scheduled,
            status="pending",
            notes=notes,
        )
        self.session.add(c)
        await self.session.flush()
        await NotificationService(self.session).notify(
            user_id=user.id,
            kind="system",
            title="Sesi BK terjadwal",
            body=f"Konsultasi dengan {counselor} dijadwalkan. Cek detail di menu Karier.",
        )
        return c

    async def cancel_consultation(
        self, user_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> Consultation:
        c = await self.session.get(Consultation, consultation_id)
        if c is None or c.user_id != user_id:
            raise NotFoundError("Consultation not found")
        c.status = "cancelled"
        await self.session.flush()
        return c

    def counselors(self) -> list[dict]:
        return [{"name": n, "role": r, "focus": f} for n, r, f in CONSULTANTS]

    # --- resources ---------------------------------------------------------
    async def ensure_resources(self) -> None:
        for code, cat, title, desc, provider, free, tags in RESOURCE_CATALOG:
            exists = (
                await self.session.execute(select(ResourceItem).where(ResourceItem.code == code))
            ).scalar_one_or_none()
            if exists is None:
                self.session.add(
                    ResourceItem(
                        code=code,
                        category=cat,
                        title=title,
                        description=desc,
                        provider=provider,
                        is_free=free,
                        tags=tags,
                    )
                )
        await self.session.flush()

    async def list_resources(
        self,
        category: str | None = None,
        major: str | None = None,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[ResourceItem]:
        stmt = select(ResourceItem).order_by(ResourceItem.category, ResourceItem.title)
        if category:
            stmt = stmt.where(ResourceItem.category == category)
        items = list((await self.session.execute(stmt)).scalars().all())
        if major:
            # Relevant-first ordering: resources tagged with the student's major
            # float to the top without hiding the rest of the catalog.
            m = major.lower()

            def _rank(item: ResourceItem) -> tuple[int, str]:
                tagged = any(m in (t or "").lower() for t in item.tags or [])
                return (0 if tagged else 1, item.title)

            items.sort(key=_rank)
        # Page the (sorted) result so the major-relevant ordering is preserved.
        return items[offset : offset + limit]

    # --- assistant ---------------------------------------------------------
    async def assistant_reply(self, user: User, question: str) -> dict:
        """Answer a career/study question.

        When a real AI provider is configured (``AI_PROVIDER=openai``/``gemini``)
        we ask the model first; any failure or a mock provider falls back to the
        deterministic rule-based knowledge base below, so the assistant always
        answers offline too.
        """
        ai = await self._ai_assistant_reply(user, question)
        if ai is not None:
            return ai
        return await self._kb_assistant_reply(user, question)

    async def _ai_assistant_reply(self, user: User, question: str) -> dict | None:
        """Try the configured LLM provider; return None to use the KB fallback."""
        from app.ai.provider import QAContext, get_ai_provider
        from app.core.config import settings

        if settings.ai_provider == "mock":
            return None
        provider = get_ai_provider()
        context = (
            f'Nama kamu adalah "{settings.assistant_name}". '
            "Kamu adalah asisten bimbingan belajar & karier untuk pelajar Indonesia: "
            "bantu soal jurusan, kampus, jalur masuk (SNBP/SNBT), dan prospek karier. "
            "Jawab ringkas, ramah, dan dalam bahasa pengguna. Jangan menyebut nama lain "
            "selain namamu."
        )
        try:
            result = await provider.answer(
                QAContext(text=context, question=question, language="id")
            )
        except Exception as exc:  # provider/network/schema failure → KB fallback
            log.warning("assistant_ai_failed", error=str(exc))
            return None
        answer = (result.answer or "").strip()
        if not answer:
            return None
        return {"answer": answer, "confidence_bp": result.confidence_bp}

    async def _kb_assistant_reply(self, user: User, question: str) -> dict:
        """Rule-based fallback: score every KB entry and return the best match.

        Matching is word-boundary based (so "protes" does not match "tes") and
        scored by how many distinct keywords hit, rather than first-match-wins.
        The personalisation branch reads the user's own data.
        """
        from app.core.config import settings

        q = (question or "").lower()
        words = set(re.findall(r"\w+", q))

        kb: list[tuple[tuple[str, ...], str]] = [
            (
                ("siapa", "qlo", "qloot", "pembuat", "nama"),
                (
                    f"Saya **{settings.assistant_name}** — asisten bimbingan belajar & "
                    "karier untuk membantu menjelajahi jurusan, kampus, jalur masuk "
                    "(SNBP/SNBT) dan prospek karir."
                ),
            ),
            (
                ("snbp", "snmptn", "prestasi", "rapor"),
                (
                    "**SNBP** adalah jalur masuk PTN tanpa tes, berdasarkan nilai rapor, "
                    "prestasi, dan portofolio. Sekolah mengisi PDSS dan siswa harus eligible."
                ),
            ),
            (
                ("snbt", "sbmptn", "utbk", "tes"),
                (
                    "**SNBT** berdasarkan hasil UTBK (TPS, literasi, penalaran matematika). "
                    "Siapkan 4-6 bulan, latihan soal harian, dan try out rutin."
                ),
            ),
            (
                ("informatika", "komputer", "programmer", "software"),
                (
                    "**Ilmu Komputer** memiliki prospek luas: Software Engineer, Data "
                    "Scientist, AI Engineer. Kampus: ITB, UI, BINUS, ITS."
                ),
            ),
            (
                ("universitas", "kampus", "ptn"),
                (
                    "Kampus teknik terbaik: ITB, ITS, UI, UGM. Untuk vokasi: Politeknik Negeri. "
                    "Pilih sesuai jurusan target dan biaya."
                ),
            ),
            (
                ("elektro",),
                (
                    "**Teknik Elektro** mempelajari listrik, elektronika dan elektromagnetika. "
                    "Prospek: engineer energi, IoT specialist. Butuh matematika & fisika kuat."
                ),
            ),
            (
                ("kimia",),
                (
                    "**Kimia** mencakup stoikiometri, larutan, dan reaksi. "
                    "Latihan soal bertahap dan gunakan Resource Library QLoot untuk memperkuat."
                ),
            ),
            (
                ("kedokteran", "dokter", "medis"),
                (
                    "**Kedokteran** menuntut Biologi & Kimia kuat serta kehati-hatian tinggi. "
                    "Kampus: UI, UGM, Unair. Siapkan SNBT dan try out intensif."
                ),
            ),
            (
                ("psikologi",),
                (
                    "**Psikologi** menonjol untuk yang ramah dan terbuka: Psikolog klinis, HR, "
                    "Researcher. Kampus: UI, UGM, Unpad."
                ),
            ),
        ]

        # Score by distinct keyword hits (word-boundary), tie-break by KB order.
        best_answer: str | None = None
        best_hits = 0
        for keys, answer in kb:
            hits = sum(1 for k in keys if k in words)
            if hits > best_hits:
                best_hits, best_answer = hits, answer
        if best_answer is not None:
            return {"answer": best_answer, "confidence_bp": min(9500, 7000 + best_hits * 800)}

        # Personalised branch: use the student's own recommendations if present.
        if {"jurusan", "rekomendasi", "karier", "karir", "major"} & words:
            recs = await self.list_recommendations(user.id)
            if recs:
                top = ", ".join(f"{r.major} ({r.fit_score}%)" for r in recs[:3])
                return {
                    "answer": (
                        f"Berdasarkan nilai & kepribadianmu, jurusan teratas: {top}. "
                        "Lihat detail di menu **Jalur Karier → Analisis**."
                    ),
                    "confidence_bp": 9000,
                }
            return {
                "answer": (
                    "Kamu belum punya analisis. Isi nilai rapor dan tes kepribadian, lalu buka "
                    "**Jalur Karier → Analisis** untuk rekomendasi personal."
                ),
                "confidence_bp": 7500,
            }

        return {
            "answer": (
                "Saya bisa membantu seputar: rekomendasi jurusan, SNBP vs SNBT, "
                "prospek karir, dan kampus terbaik. Coba tanyakan salah satunya."
            ),
            "confidence_bp": 5000,
        }
