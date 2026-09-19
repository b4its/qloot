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

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
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


class CareerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- grades ------------------------------------------------------------
    async def list_grades(self, user_id: uuid.UUID) -> list[AcademicGrade]:
        stmt = (
            select(AcademicGrade)
            .where(AcademicGrade.user_id == user_id)
            .order_by(AcademicGrade.subject)
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
        subjects = [{"subject": g.subject, "grade": g.grade} for g in grades]
        avg = _clamp(sum(g.grade for g in grades) / len(grades))
        ordered = sorted(grades, key=lambda g: g.grade)
        weak, strong = ordered[0], ordered[-1]

        # Simulated 6-month trend toward the current average.
        months = ["Feb", "Mar", "Apr", "Mei", "Jun", "Jul"]
        trend = []
        for i, m in enumerate(months):
            value = avg - (len(months) - 1 - i) * 1.6
            trend.append({"month": m, "value": _clamp(value)})

        # Radar: interest spread across 6 study areas (simulated from grades).
        radar = self._radar_from_grades(grades)

        insights = [
            {
                "kind": "consistency",
                "title": f"{strong.subject} konsisten kuat",
                "detail": f"Nilai {strong.subject} tertinggi ({strong.grade}). Pertahankan.",
            },
            {
                "kind": "attention",
                "title": f"{weak.subject} perlu perhatian",
                "detail": f"Nilai {weak.subject} terendah ({weak.grade}). Fokus penguatan.",
            },
            {
                "kind": "potential",
                "title": "Proyeksi jurusan optimal",
                "detail": "Kombinasi nilai eksakta dan minat cocok untuk rumpun teknik/sains.",
            },
        ]
        return {
            "average": avg,
            "strong_subject": strong.subject,
            "weak_subject": weak.subject,
            "subjects": subjects,
            "trend": trend,
            "radar": radar,
            "insights": insights,
        }

    def _radar_from_grades(self, grades: list[AcademicGrade]) -> list[dict]:
        by_subject = {g.subject: g.grade for g in grades}
        dims = {
            "Sains": by_subject.get("Fisika", 75),
            "Teknik": by_subject.get("Matematika", 75),
            "Bahasa": by_subject.get("B. Inggris", 75),
            "Seni": 70,
            "Sosial": by_subject.get("B. Indonesia", 75),
            "Bisnis": by_subject.get("Matematika", 72),
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

        Deterministic: answers are folded into five trait sums.
        """
        if len(answers) < 5:
            raise ConflictError("At least 5 answers are required")
        n = len(answers)
        # Distribute answers round-robin across the five traits.
        buckets: dict[str, list[int]] = {t: [] for t in TRAITS}
        for i, ans in enumerate(answers):
            trait = TRAITS[i % 5]
            buckets[trait].append(max(1, min(5, int(ans))))

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
        top = max(
            [
                ("Keterbukaan", result.openness),
                ("Kehati-hatian", result.conscientiousness),
                ("Ekstroversi", result.extraversion),
                ("Keramahan", result.agreeableness),
            ],
            key=lambda x: x[1],
        )
        result.summary = (
            f"Profil menonjol pada {top[0]} ({top[1]}). "
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
        grades = {g.subject: g.grade for g in await self.list_grades(user.id)}
        personality = await self.latest_personality(user.id)

        scored: list[tuple[float, dict, int, int]] = []
        for major in MAJOR_CATALOG:
            academic = 0.0
            weight_sum = 0.0
            for subject, weight in major["subjects"].items():
                weight_sum += weight
                academic += grades.get(subject, 70) * weight
            academic_score = academic / (weight_sum or 1)

            personality_score = 60.0
            if personality is not None:
                pts = 0.0
                wsum = 0.0
                for trait, weight in major["traits"].items():
                    value = getattr(personality, trait)
                    # Negative weight means "lower is better" (e.g. neuroticism).
                    contribution = value if weight >= 0 else (100 - value)
                    pts += contribution * abs(weight)
                    wsum += abs(weight)
                personality_score = pts / (wsum or 1)

            fit = academic_score * 0.6 + personality_score * 0.4
            scored.append((fit, major, _clamp(academic_score), _clamp(personality_score)))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Clear prior drafts and regenerate.
        prior = (
            (
                await self.session.execute(
                    select(CareerRecommendation).where(CareerRecommendation.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        for row in prior:
            await self.session.delete(row)
        await self.session.flush()

        results: list[CareerRecommendation] = []
        for rank, (fit, major, academic_fit, personality_fit) in enumerate(scored[:top_n], start=1):
            rec = CareerRecommendation(
                user_id=user.id,
                major=major["major"],
                fit_score=_clamp(fit),
                academic_fit=academic_fit,
                personality_fit=personality_fit,
                rationale=(f"Kombinasi nilai akademik dan kepribadian mendukung {major['major']}."),
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

    async def list_recommendations(self, user_id: uuid.UUID) -> list[CareerRecommendation]:
        stmt = (
            select(CareerRecommendation)
            .where(CareerRecommendation.user_id == user_id)
            .order_by(CareerRecommendation.rank)
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

    async def approve(self, user: User) -> int:
        recs = await self.list_recommendations(user.id)
        if not recs:
            raise NotFoundError("No recommendations to approve")
        for r in recs:
            r.status = "approved"
        if not await self.list_milestones(user.id):
            await self._build_roadmap(user, recs[0].major)
        await NotificationService(self.session).notify(
            user_id=user.id,
            kind="system",
            title="Roadmap diaktifkan",
            body="Selamat! Roadmap jalur studi Anda telah disahkan.",
        )
        await self.session.flush()
        return len(recs)

    # --- roadmap -----------------------------------------------------------
    async def list_milestones(self, user_id: uuid.UUID) -> list[RoadmapMilestone]:
        stmt = (
            select(RoadmapMilestone)
            .where(RoadmapMilestone.user_id == user_id)
            .order_by(RoadmapMilestone.position)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _build_roadmap(self, user: User, major: str) -> list[RoadmapMilestone]:
        specs = [
            (
                "Sekarang - 3 Bulan",
                "Penguatan Fondasi Akademik",
                f"Fokus memperkuat mata pelajaran inti untuk {major}.",
                ["Les tambahan 2x/minggu", "Latihan soal mandiri"],
                45,
                "in_progress",
            ),
            (
                "4 - 8 Bulan",
                "Eksplorasi Proyek & Kompetisi",
                "Ikut olimpiade atau proyek untuk membangun portofolio.",
                ["Daftar olimpiade", "Proyek sederhana"],
                0,
                "not_started",
            ),
            (
                "9 - 12 Bulan",
                "Persiapan Seleksi Masuk PTN",
                "Simulasi ujian masuk dan pendaftaran kampus target.",
                ["Try out bulanan", "Bimbel SBMPTN"],
                0,
                "not_started",
            ),
        ]
        created: list[RoadmapMilestone] = []
        for i, (period, title, desc, tasks, prog, status) in enumerate(specs):
            m = RoadmapMilestone(
                user_id=user.id,
                title=title,
                description=desc,
                period=period,
                position=i,
                progress_percent=prog,
                status=status,
                tasks=tasks,
            )
            self.session.add(m)
            created.append(m)
        await self.session.flush()
        return created

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
    async def list_consultations(self, user_id: uuid.UUID) -> list[Consultation]:
        stmt = (
            select(Consultation)
            .where(Consultation.user_id == user_id)
            .order_by(Consultation.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_consultation(
        self, user: User, *, counselor: str, topic: str, notes: str | None
    ) -> Consultation:
        c = Consultation(
            user_id=user.id,
            counselor=counselor,
            topic=topic,
            scheduled_at=datetime.now(UTC) + timedelta(days=3),
            status="pending",
            notes=notes,
        )
        self.session.add(c)
        await self.session.flush()
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

    async def list_resources(self, category: str | None = None) -> list[ResourceItem]:
        stmt = select(ResourceItem).order_by(ResourceItem.category, ResourceItem.title)
        if category:
            stmt = stmt.where(ResourceItem.category == category)
        return list((await self.session.execute(stmt)).scalars().all())

    # --- assistant ---------------------------------------------------------
    def assistant_reply(self, question: str) -> dict:
        q = question.lower()
        kb = [
            (
                ("siapa", "kamu", "qlo ot", "qloot", "pembuat"),
                (
                    "Saya **QLoot AI Assistant** — asisten simulasi untuk membantu "
                    "menjelajahi jurusan, kampus, jalur masuk (SNBP/SNBT) dan prospek karir."
                ),
            ),
            (
                ("snbp", "snmptn", "prestasi"),
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
                ("informatika", "komputer", "prospek", "programmer"),
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
                ("kimia", "perhatian", "lemah"),
                (
                    "Untuk memperkuat Kimia: fokus stoikiometri & larutan, latihan soal "
                    "bertahap, dan gunakan Resource Library QLoot."
                ),
            ),
        ]
        for keys, answer in kb:
            if any(k in q for k in keys):
                return {"answer": answer, "confidence_bp": 8500}
        if "jurusan" in q or "rekomendasi" in q:
            return {
                "answer": (
                    "Rekomendasi umum untuk rumpun IPA: Teknik Elektro, Ilmu Komputer, "
                    "dan Kedokteran. Buka menu **Jalur Karier → Analisis** untuk "
                    "rekomendasi personal berdasarkan nilai & kepribadian Anda."
                ),
                "confidence_bp": 7800,
            }
        return {
            "answer": (
                "Saya bisa membantu seputar: rekomendasi jurusan, SNBP vs SNBT, "
                "prospek karir, dan kampus terbaik. Coba tanyakan salah satunya."
            ),
            "confidence_bp": 5000,
        }
