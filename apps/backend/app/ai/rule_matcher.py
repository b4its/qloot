"""Rule-based and fuzzy-matching knowledge engine for QLoot AI.

Provides deterministic, offline, and fuzzy-tolerant question answering
covering university admissions (SNBP, SNBT, UTBK, Mandiri), academic majors,
career prospects, campus recommendations, scholarships (KIP Kuliah), study tips,
and platform navigation.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RuleEntry:
    id: str
    primary_keywords: tuple[str, ...]
    secondary_keywords: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    answer: str = ""
    base_confidence: int = 8000
    category: str = "general"


def normalize_text(text: str) -> str:
    """Lowercase and clean punctuation for robust token matching."""
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_tokens(text: str) -> list[str]:
    """Extract individual words with min length of 2 characters."""
    normalized = normalize_text(text)
    return [w for w in normalized.split() if len(w) >= 2]


def fuzzy_word_match(word: str, target: str, threshold: float = 0.78) -> bool:
    """Check if word is identical or close enough to target (handles typos)."""
    if word == target:
        return True
    if len(word) < 4 and len(target) < 4:
        return word == target
    if abs(len(word) - len(target)) > 3:
        return False
    ratio = difflib.SequenceMatcher(None, word, target).ratio()
    return ratio >= threshold


class RuleBasedMatcher:
    """Intelligent rule-based and fuzzy knowledge matching engine."""

    def __init__(self, assistant_name: str = "Asisten Qlo") -> None:
        self.assistant_name = assistant_name
        self.rules: list[RuleEntry] = self._build_knowledge_base()

    def _build_knowledge_base(self) -> list[RuleEntry]:
        name = self.assistant_name
        return [
            # 1. Identity & Greeting
            RuleEntry(
                id="identity",
                primary_keywords=("siapa", "nama", "qlu", "qlo", "qloot", "pembuat", "pencipta"),
                secondary_keywords=("asisten", "bot", "ai", "bantuan", "fungsi"),
                phrases=(
                    "siapa kamu",
                    "siapa anda",
                    "nama kamu",
                    "tentang qloot",
                    "apa itu qloot",
                ),
                answer=(
                    f"Saya **{name}** — asisten bimbingan belajar & panduan karier di "
                    "platform QLoot. Saya siap membantu menjawab pertanyaan seputar "
                    "pemilihan jurusan, info kampus, jalur masuk perguruan tinggi "
                    "(SNBP, SNBT, Mandiri), beasiswa, hingga prospek karier."
                ),
                base_confidence=9500,
                category="identity",
            ),
            RuleEntry(
                id="greeting",
                primary_keywords=(
                    "halo",
                    "hai",
                    "hello",
                    "hei",
                    "pagi",
                    "siang",
                    "sore",
                    "malam",
                    "assalamualaikum",
                ),
                secondary_keywords=("bantu", "tanya"),
                phrases=(
                    "halo qlu",
                    "hai qlu",
                    "halo qlo",
                    "hai qlo",
                    "selamat pagi",
                    "selamat siang",
                    "selamat sore",
                    "selamat malam",
                ),
                answer=(
                    f"Halo! Saya **{name}**. Ada yang bisa saya bantu terkait rencana kuliah, "
                    "persiapan ujian, pemilihan jurusan, atau eksplorasi karier impianmu?"
                ),
                base_confidence=8500,
                category="identity",
            ),
            # 2. Admission Paths (SNBP, SNBT, Mandiri)
            RuleEntry(
                id="snbp_vs_snbt",
                primary_keywords=("snbp", "snbt"),
                secondary_keywords=("beda", "perbedaan", "versus", "vs", "bandingkan", "pilih"),
                phrases=(
                    "beda snbp dan snbt",
                    "perbedaan snbp dan snbt",
                    "snbp vs snbt",
                    "bedanya snbp",
                ),
                answer=(
                    "**Perbedaan Utama SNBP vs SNBT:**\n\n"
                    "1. **SNBP (Jalur Prestasi):**\n"
                    "   - **Penilaian:** Nilai rapor semester 1–5, rekam jejak sekolah, dan "
                    "portofolio (seni/olahraga).\n"
                    "   - **Syarat:** Masuk siswa *eligible* (kuota 40% untuk Akreditasi A).\n"
                    "   - **Konsekuensi:** Jika lulus, tidak dapat mendaftar SNBT maupun "
                    "Jalur Mandiri PTN.\n\n"
                    "2. **SNBT (Jalur Tes / UTBK):**\n"
                    "   - **Penilaian:** Murni skor UTBK (TPS, Literasi, Penalaran Matematika).\n"
                    "   - **Syarat:** Terbuka untuk lulusan SMA/SMK/MA 3 tahun terakhir.\n\n"
                    "💡 *Strategi:* Maksimalkan SNBP jika eligible, tetapi tetap siapkan UTBK!"
                ),
                base_confidence=9600,
                category="admission",
            ),
            RuleEntry(
                id="snbp",
                primary_keywords=("snbp", "snmptn", "eligible", "pdss"),
                secondary_keywords=("rapor", "prestasi", "kuota", "sertifikat", "portofolio"),
                phrases=(
                    "jalur snbp",
                    "apa itu snbp",
                    "syarat snbp",
                    "lolos snbp",
                    "nilai rapor snbp",
                ),
                answer=(
                    "**SNBP (Seleksi Nasional Berdasarkan Prestasi)** adalah jalur masuk PTN "
                    "tanpa tes tertulis.\n\n"
                    "📌 **Komponen Penilaian:**\n"
                    "- Rata-rata nilai rapor seluruh mapel semester 1–5 (bobot minimal 50%).\n"
                    "- Nilai mapel pendukung prodi, prestasi kejuaraan, atau portofolio "
                    "(bobot maksimal 50%).\n"
                    "- Rekam jejak sekolah (akreditasi dan rekam jejak alumni di PTN).\n\n"
                    "💡 *Catatan:* Siswa yang diterima di SNBP tidak dapat mendaftar SNBT."
                ),
                base_confidence=9200,
                category="admission",
            ),
            RuleEntry(
                id="snbt_utbk",
                primary_keywords=("snbt", "sbmptn", "utbk"),
                secondary_keywords=(
                    "tes",
                    "tps",
                    "literasi",
                    "penalaran",
                    "matematika",
                    "skor",
                    "kuantitatif",
                ),
                phrases=(
                    "apa itu snbt",
                    "materi utbk",
                    "persiapan utbk",
                    "soal utbk",
                    "skor utbk",
                ),
                answer=(
                    "**SNBT (Seleksi Nasional Berdasarkan Tes)** menggunakan sistem **UTBK**.\n\n"
                    "📝 **Materi Ujian UTBK:**\n"
                    "1. **Tes Potensi Skolastik (TPS):** Penalaran Umum, Pengetahuan Umum, "
                    "Pemahaman Bacaan & Menulis, Kuantitatif.\n"
                    "2. **Literasi:** Literasi Bahasa Indonesia dan Literasi Bahasa Inggris.\n"
                    "3. **Penalaran Matematika.**\n\n"
                    "🎯 *Tips Lolos:* Siapkan belajar 4–6 bulan, kuasai konsep dasar, dan ikuti "
                    "Try Out rutin untuk melatih manajemen waktu!"
                ),
                base_confidence=9200,
                category="admission",
            ),
            RuleEntry(
                id="mandiri",
                primary_keywords=("mandiri", "simak", "utul", "smup", "cbt"),
                secondary_keywords=("seleksi", "ptn", "ujian", "biaya", "ipi", "uang pangkal"),
                phrases=("jalur mandiri", "ujian mandiri", "simak ui", "utul ugm"),
                answer=(
                    "**Jalur Mandiri PTN** diselenggarakan secara independen oleh kampus.\n\n"
                    "🔍 **Skema Seleksi:**\n"
                    "- **Menggunakan nilai UTBK:** Menggunakan skor UTBK tanpa tes ulang.\n"
                    "- **Ujian Tulis Khusus:** Contohnya SIMAK UI, UM-CBT UGM, SMUP Unpad.\n\n"
                    "💰 *Biaya:* Jalur mandiri umumnya menerapkan Iuran Pengembangan Institusi "
                    "(IPI/Uang Pangkal) selain UKT reguler. Periksa rincian di laman resmi kampus!"
                ),
                base_confidence=9000,
                category="admission",
            ),
            # 3. Majors: Technology & Computer Science
            RuleEntry(
                id="cs_it",
                primary_keywords=("informatika", "komputer", "programmer", "software"),
                secondary_keywords=("coding", "data", "developer", "koding", "cyber", "ai"),
                phrases=(
                    "ilmu komputer",
                    "teknik informatika",
                    "sistem informasi",
                    "prospek informatika",
                ),
                answer=(
                    "**Ilmu Komputer & Teknik Informatika:**\n\n"
                    "💻 **Fokus Studi:** Algoritma, struktur data, rekayasa perangkat lunak, "
                    "basis data, AI, dan keamanan siber.\n"
                    "🚀 **Prospek Karier:** Software Engineer, Data Scientist, AI Specialist, "
                    "Cloud Architect, DevOps, Product Manager.\n"
                    "🏛️ **Kampus Unggulan:** ITB, UI, ITS, UGM, BINUS, Telkom University.\n\n"
                    "💡 *Tips:* Bangun portofolio proyek di GitHub dan latih problem solving!"
                ),
                base_confidence=9200,
                category="major",
            ),
            # 4. Majors: Medicine & Healthcare
            RuleEntry(
                id="medicine",
                primary_keywords=("kedokteran", "dokter", "medis"),
                secondary_keywords=("farmasi", "gigi", "perawat", "koas", "kesehatan"),
                phrases=(
                    "pendidikan dokter",
                    "kuliah kedokteran",
                    "masuk kedokteran",
                    "fakultas kedokteran",
                ),
                answer=(
                    "**Pendidikan Dokter & Ilmu Kedokteran:**\n\n"
                    "🩺 **Karakteristik Studi:** Memerlukan fondasi Biologi & Kimia yang kuat, "
                    "daya tahan belajar tinggi, dan empati.\n"
                    "⏳ **Tahapan:** Sarjana Kedokteran (S.Ked ±3.5–4 th) ➔ Profesi Dokter / Koas "
                    "(±1.5–2 th) ➔ Uji Kompetensi (UKMPPD) ➔ Internship (1 th).\n"
                    "🏛️ **Kampus Favorit:** UI, UGM, Unair, Undip, Unpad, Unhas.\n\n"
                    "💡 *Strategi:* Passing grade sangat tinggi; optimalkan try out intensif."
                ),
                base_confidence=9200,
                category="major",
            ),
            # 5. Majors: Engineering
            RuleEntry(
                id="engineering",
                primary_keywords=("elektro", "mesin", "sipil", "industri", "arsitektur"),
                secondary_keywords=("teknik", "rekayasa", "fisika", "manufaktur"),
                phrases=(
                    "fakultas teknik",
                    "jurusan teknik",
                    "teknik elektro",
                    "teknik mesin",
                    "teknik sipil",
                ),
                answer=(
                    "**Rumpun Teknik (Engineering):**\n\n"
                    "⚙️ **Pilihan Utama:**\n"
                    "- **Teknik Elektro:** Elektronika, tenaga listrik, telekomunikasi, IoT.\n"
                    "- **Teknik Mesin:** Termodinamika, perancangan mesin, otomotif, energi.\n"
                    "- **Teknik Sipil:** Konstruksi, struktur gedung, jalan, jembatan.\n"
                    "- **Teknik Industri:** Optimasi manufaktur, supply chain, manajemen mutu.\n"
                    "🏛️ **Kampus Top:** ITB, ITS, UI, UGM, Undip.\n\n"
                    "💡 *Syarat Kunci:* Memerlukan matematika kalkulus dan logika fisika kuat."
                ),
                base_confidence=9200,
                category="major",
            ),
            # 6. Majors: Sciences (MIPA)
            RuleEntry(
                id="sciences",
                primary_keywords=(
                    "kimia",
                    "fisika",
                    "biologi",
                    "matematika",
                    "aktuaria",
                    "statistika",
                ),
                secondary_keywords=("mipa", "sains", "analis", "laboratorium"),
                phrases=("fakultas mipa", "jurusan mipa", "ilmu mipa", "sains data"),
                answer=(
                    "**Rumpun Sains & Matematika (FMIPA):**\n\n"
                    "🔬 **Peluang & Keunggulan:**\n"
                    "- **Aktuaria & Statistika:** Sangat dicari di industri keuangan, fintech, "
                    "dan data science.\n"
                    "- **Kimia & Biologi:** Riset farmasi, bioteknologi, dan kontrol mutu.\n"
                    "- **Fisika & Matematika:** Fondasi komputasi kuantum, riset energi & model "
                    "analitik.\n"
                    "🏛️ **Kampus Unggulan:** ITB, UGM, UI, ITS, Unair.\n\n"
                    "💡 Gunakan Resource Library di QLoot untuk melatih penguasaan konsep sains!"
                ),
                base_confidence=9200,
                category="major",
            ),
            # 7. Majors: Economics, Business, Management
            RuleEntry(
                id="business",
                primary_keywords=("manajemen", "akuntansi", "ekonomi", "bisnis"),
                secondary_keywords=("keuangan", "finance", "marketing", "bank", "perbankan"),
                phrases=(
                    "fakultas ekonomi",
                    "jurusan bisnis",
                    "jurusan manajemen",
                    "jurusan akuntansi",
                ),
                answer=(
                    "**Fakultas Ekonomika dan Bisnis (FEB):**\n\n"
                    "📊 **Pilihan Jurusan:**\n"
                    "- **Akuntansi:** Audit, pelaporan keuangan, pajak. Prospek: Big 4, "
                    "Financial Controller.\n"
                    "- **Manajemen & Bisnis:** Pemasaran, keuangan, SDM, startup, konsultan "
                    "bisnis.\n"
                    "- **Ilmu Ekonomi:** Kebijakan moneter/fiskal, analis ekonomi, perbankan.\n"
                    "🏛️ **Kampus Unggulan:** UI, UGM, SBM ITB, Unpad, Undip, Brawijaya."
                ),
                base_confidence=9100,
                category="major",
            ),
            # 8. Majors: Psychology & Social Sciences
            RuleEntry(
                id="social_psychology",
                primary_keywords=("psikologi", "hukum", "komunikasi", "hubungan internasional"),
                secondary_keywords=("soshum", "sosial", "humaniora", "desain"),
                phrases=("jurusan psikologi", "jurusan hukum", "ilmu komunikasi"),
                answer=(
                    "**Rumpun Sosial & Humaniora (Soshum):**\n\n"
                    "🧠 **Sorotan Program Studi:**\n"
                    "- **Psikologi:** Mempelajari perilaku manusia. Prospek: HR, Psikolog, "
                    "Peneliti (UI, UGM, Unpad).\n"
                    "- **Ilmu Hukum:** Hukum bisnis, peradilan, korporasi, diplomat (UI, UGM, "
                    "Undip, Unair).\n"
                    "- **Ilmu Komunikasi:** Public relations, media digital, jurnalistik "
                    "(UI, UGM, Unpad)."
                ),
                base_confidence=9100,
                category="major",
            ),
            # 9. Campus Recommendations (PTN, PTS, Politeknik)
            RuleEntry(
                id="campuses",
                primary_keywords=("universitas", "kampus", "ptn", "pts", "politeknik"),
                secondary_keywords=("negeri", "swasta", "kuliah", "terbaik", "rekomendasi"),
                phrases=(
                    "kampus terbaik",
                    "universitas terbaik",
                    "ptn terbaik",
                    "rekomendasi kampus",
                    "politeknik negeri",
                ),
                answer=(
                    "**Panduan Memilih Kampus:**\n\n"
                    "🏛️ **PTN Terkemuka:**\n"
                    "- **Teknik & Sains:** ITB, ITS, UI, UGM, Undip.\n"
                    "- **Kedokteran:** UI, UGM, Unair, Unpad, Undip, Unhas.\n"
                    "- **Bisnis & Soshum:** UI, UGM, Unpad, SBM ITB, Brawijaya.\n\n"
                    "🎓 **Politeknik (Vokasi):** 60–70% praktikum kerja (PENS, Polban, PNJ).\n"
                    "🌟 **PTS Favorit:** BINUS, Telkom University, UII, Atma Jaya, Trisakti.\n\n"
                    "💡 *Kriteria:* Cek akreditasi prodi, biaya UKT, lokasi, dan rekam jejak "
                    "alumni."
                ),
                base_confidence=9200,
                category="campus",
            ),
            # 10. Scholarships & Financial Aid
            RuleEntry(
                id="scholarship_kip",
                primary_keywords=("beasiswa", "kip", "ukt"),
                secondary_keywords=("gratis", "bantuan", "biaya", "kuliah", "keringanan"),
                phrases=("kip kuliah", "beasiswa kuliah", "keringanan ukt", "biaya kuliah"),
                answer=(
                    "**Beasiswa & Pembiayaan Kuliah:**\n\n"
                    "🎓 **KIP Kuliah:**\n"
                    "- Bantuan pemerintah untuk siswa berprestasi dengan keterbatasan ekonomi.\n"
                    "- **Manfaat:** Pembebasan biaya pendaftaran, bebas biaya kuliah (UKT) 100%, "
                    "dan bantuan biaya hidup bulanan.\n\n"
                    "✨ **Beasiswa Lainnya:** Beasiswa Indonesia Maju (BIM), Beasiswa Unggulan, "
                    "dan beasiswa korporat (BCA, Djarum). Sistem UKT PTN bergradasi sesuai "
                    "kemampuan."
                ),
                base_confidence=9300,
                category="scholarship",
            ),
            # 11. Study Tips & Exam Strategies
            RuleEntry(
                id="study_tips",
                primary_keywords=("tips", "strategi", "cara", "jadwal"),
                secondary_keywords=("belajar", "utbk", "tryout", "fokus", "konsisten", "burnout"),
                phrases=(
                    "tips belajar",
                    "cara belajar",
                    "tips utbk",
                    "jadwal belajar",
                    "mengatasi burnout",
                ),
                answer=(
                    "**Tips Belajar Efektif & Lolos Ujian:**\n\n"
                    "1. **Active Recall & Spaced Repetition:** Latih diri dengan mengerjakan soal "
                    "tanpa melihat rangkuman catatan.\n"
                    "2. **Evaluasi Try Out:** Bedah setiap soal yang salah untuk mengenali materi "
                    "yang belum dipahami.\n"
                    "3. **Metode Pomodoro:** Belajar fokus 25–45 menit diselingi rehat 5 menit.\n"
                    "4. **Manajemen Waktu:** Jangan terjebak lebih dari 1 menit pada soal buntu.\n"
                    "5. **Jaga Kesehatan:** Tidur cukup 7–8 jam sebelum ujian sangat krusial!"
                ),
                base_confidence=9000,
                category="tips",
            ),
            # 12. QLoot Platform & Ecosystem
            RuleEntry(
                id="qloot_platform",
                primary_keywords=(
                    "token",
                    "opt",
                    "qtc",
                    "ort",
                    "wallet",
                    "dompet",
                    "sertifikat",
                    "quest",
                ),
                secondary_keywords=("qloot", "onchain", "blockchain", "hadiah", "kelas"),
                phrases=(
                    "token qloot",
                    "cara dapat token",
                    "sertifikat qloot",
                    "quest qloot",
                ),
                answer=(
                    "**Ekosistem Pembelajaran QLoot:**\n\n"
                    "🪙 **Token Pembelajaran:**\n"
                    "- **OPT (On-Chain Proof Token):** Diperoleh dari modul dan lulus ujian.\n"
                    "- **QTC (Quest Token Credit):** Diperoleh dari memenangkan Quest.\n"
                    "- **ORT (Open Resource Token):** Digunakan untuk akses asisten Qlo.\n\n"
                    "📜 **Sertifikat Digital:** Sertifikat terverifikasi on-chain (ERC-1155) yang "
                    "membuktikan kompetensimu secara permanen dan transparan."
                ),
                base_confidence=9200,
                category="platform",
            ),
        ]

    def match(self, question: str) -> dict | None:
        """Find the best rule match using exact phrases, keyword hits, and fuzzy tokens."""
        if not question or not question.strip():
            return None

        q_norm = normalize_text(question)
        q_tokens = extract_tokens(question)
        if not q_tokens:
            return None

        best_rule: RuleEntry | None = None
        best_score = 0.0

        for rule in self.rules:
            score = 0.0

            # 1. Exact phrase matches (highest signal)
            for phrase in rule.phrases:
                phrase_norm = normalize_text(phrase)
                if phrase_norm and phrase_norm in q_norm:
                    score += 5.0

            # 2. Primary keyword matches (exact or fuzzy)
            primary_matches = 0
            for pk in rule.primary_keywords:
                matched = False
                for token in q_tokens:
                    if fuzzy_word_match(token, pk):
                        matched = True
                        break
                if matched:
                    primary_matches += 1

            if primary_matches > 0:
                score += primary_matches * 3.0

            # 3. Secondary keyword matches
            secondary_matches = 0
            for sk in rule.secondary_keywords:
                matched = False
                for token in q_tokens:
                    if fuzzy_word_match(token, sk):
                        matched = True
                        break
                if matched:
                    secondary_matches += 1

            if secondary_matches > 0:
                score += secondary_matches * 1.0

            if (primary_matches > 0 or score >= 5.0) and score > best_score:
                best_score = score
                best_rule = rule

        if best_rule is not None and best_score >= 3.0:
            confidence = min(9800, best_rule.base_confidence + int(min(best_score * 100, 800)))
            return {
                "answer": best_rule.answer,
                "confidence_bp": confidence,
                "rule_id": best_rule.id,
                "category": best_rule.category,
            }

        return None

    def fallback_guide(self) -> dict:
        """Friendly default response when a question cannot be resolved."""
        return {
            "answer": (
                f"Saya **{self.assistant_name}** dapat membantu pertanyaan seputar:\n\n"
                "1. **Jalur Masuk PTN:** Info SNBP, materi & strategi SNBT UTBK, dan Mandiri.\n"
                "2. **Pilihan Jurusan:** Ilmu Komputer, Kedokteran, Teknik, MIPA, Bisnis, Soshum.\n"
                "3. **Rekomendasi Kampus:** PTN terbaik, PTS favorit, dan politeknik vokasi.\n"
                "4. **Finansial & Beasiswa:** Info KIP Kuliah, beasiswa, dan panduan UKT.\n"
                "5. **Tips Belajar:** Strategi belajar efektif dan manajemen waktu ujian.\n\n"
                "Silakan ketik pertanyaan spesifik, misalnya: *'Apa bedanya SNBP dan SNBT?'* "
                "atau *'Bagaimana prospek kerja jurusan Informatika?'*."
            ),
            "confidence_bp": 5500,
        }
