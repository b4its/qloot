"""Realistic, curriculum-shaped demo content for the QLoot seeder.

This module is a *data catalog* — it owns the human-authored material that the
seeders weave into a coherent demo. Keeping it separate from the seeding logic
means the "what" (Indonesian SMA curriculum content) never gets tangled with the
"how" (idempotent inserts, deterministic ids, time distribution).

Design goals:
  - **Realistic**: real Indonesian senior-high subjects, semester terms, lesson
    titles and multiple-choice questions a student would actually see, instead of
    the old ``Matematika — Kelas 1A #001`` filler.
  - **Flow-faithful**: a subject ("pelajaran") belongs to one (class_code,
    class_type); it has ordered lessons; an exam/quiz is attached to a subject;
    completing every lesson issues a certificate. The time-line seeder replays
    this flow month by month.
  - **Deterministic**: every helper derives stable data from an index/seed, so
    re-seeding yields identical rows (uuid5 ids are computed from these).

Nothing here touches the database — it is pure data + tiny pure helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


class MajorSpec(TypedDict):
    major: str
    universities: list[str]
    admission_paths: list[str]
    skills: list[str]
    careers: list[str]
    rationale_best_for: list[str]


class ResourceSpec(TypedDict):
    code: str
    category: str
    title: str
    description: str
    provider: str
    is_free: bool
    tags: list[str]

# ---------------------------------------------------------------------------
# Classes / programmes (rombel)
# ---------------------------------------------------------------------------
# (class_code, class_type). Two intakes per grade so the roster looks real.
CLASSES: list[tuple[str, str]] = [
    ("10A", "IPA"),
    ("10B", "IPS"),
    ("11A", "IPA"),
    ("11B", "IPS"),
    ("12A", "IPA"),
    ("12B", "IPS"),
]

# Academic terms, newest last. Used for report-card grades and to date content.
TERMS: list[str] = [
    "2024/2025-ganjil",
    "2024/2025-genap",
    "2025/2026-ganjil",
    "2025/2026-genap",
]


# ---------------------------------------------------------------------------
# Lesson bank, keyed by subject. Each lesson is (title, markdown body).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LessonSpec:
    title: str
    body: str


def _lesson(title: str, body: str) -> LessonSpec:
    return LessonSpec(title=title, body=body)


SUBJECT_LESSONS: dict[str, list[LessonSpec]] = {
    "Matematika": [
        _lesson(
            "Bilangan Berpangkat & Bentuk Akar",
            "# Bilangan Berpangkat\n\n"
            "Sifat-sifat eksponen: $a^m \\cdot a^n = a^{m+n}$ dan $(a^m)^n = a^{mn}$.\n\n"
            "**Contoh:** $2^3 \\cdot 2^4 = 2^7 = 128$. Bentuk akar $\\sqrt{a}$ "
            "adalah kebalikan dari pemangkatan pecahan.",
        ),
        _lesson(
            "Persamaan & Pertidaksamaan Linear",
            "# Persamaan Linear\n\n"
            "Bentuk umum $ax + b = 0$. Selesaikan dengan memindahkan suku.\n\n"
            "**Contoh:** $3x + 6 = 0 \\Rightarrow x = -2$. Pertidaksamaan "
            "mengubah tanda saat dikali/dibagi bilangan negatif.",
        ),
        _lesson(
            "Barisan & Deret Aritmetika",
            "# Barisan Aritmetika\n\n"
            "Suku ke-n: $U_n = a + (n-1)b$. Jumlah n suku: "
            "$S_n = \\tfrac{n}{2}(2a + (n-1)b)$.\n\n"
            "**Contoh:** 2, 5, 8, … memiliki $b=3$ sehingga $U_{10}=29$.",
        ),
        _lesson(
            "Fungsi Kuadrat",
            "# Fungsi Kuadrat\n\n"
            "$f(x) = ax^2 + bx + c$ dengan $a \\neq 0$. Titik puncak "
            "$x_p = -\\tfrac{b}{2a}$. Diskriminan $D = b^2 - 4ac$ menentukan "
            "jumlah akar real.",
        ),
        _lesson(
            "Statistika: Ukuran Pemusatan",
            "# Statistika\n\n"
            "Mean = jumlah data / banyak data. Median = nilai tengah data "
            "terurut. Modus = nilai paling sering muncul.",
        ),
        _lesson(
            "Peluang Kejadian Majemuk",
            "# Peluang\n\n"
            "$P(A) = \\tfrac{n(A)}{n(S)}$. Dua kejadian saling bebas memenuhi "
            "$P(A \\cap B) = P(A) \\cdot P(B)$.",
        ),
    ],
    "Fisika": [
        _lesson(
            "Kinematika Gerak Lurus",
            "# Kinematika\n\n"
            "GLB: $s = v \\cdot t$. GLBB: $v_t = v_0 + at$ dan "
            "$s = v_0 t + \\tfrac{1}{2} a t^2$.",
        ),
        _lesson(
            "Hukum Newton & Dinamika",
            "# Hukum Newton\n\nI: benda diam tetap diam. II: $\\sum F = ma$. III: aksi = reaksi.",
        ),
        _lesson(
            "Usaha, Energi & Daya",
            "# Usaha & Energi\n\n"
            "$W = F \\cdot s \\cdot \\cos\\theta$. Energi kinetik "
            "$E_k = \\tfrac{1}{2} m v^2$; potensial $E_p = mgh$.",
        ),
        _lesson(
            "Getaran & Gelombang",
            "# Gelombang\n\n"
            "Periode $T = 1/f$, cepat rambat $v = \\lambda f$. Bunyi termasuk "
            "gelombang mekanik longitudinal.",
        ),
        _lesson(
            "Listrik Dinamis",
            "# Listrik Dinamis\n\n"
            "Hukum Ohm $V = IR$. Daya listrik $P = VI = I^2R$. Rangkaian seri "
            "menjumlah hambatan; paralel memakai $1/R_p = \\sum 1/R_i$.",
        ),
    ],
    "Kimia": [
        _lesson(
            "Struktur Atom",
            "# Struktur Atom\n\n"
            "Atom tersusun dari proton, neutron, dan elektron. Konfigurasi "
            "elektron mengikuti aturan Aufbau.",
        ),
        _lesson(
            "Ikatan Kimia",
            "# Ikatan Kimia\n\n"
            "Ikatan ion terjadi serah-terima elektron; ikatan kovalen "
            "memakai pemakaian bersama pasangan elektron.",
        ),
        _lesson(
            "Stoikiometri",
            "# Stoikiometri\n\n"
            "Mol = massa / massa molar. Perbandingan koefisien reaksi setara "
            "dengan perbandingan mol.",
        ),
        _lesson(
            "Larutan Asam-Basa",
            "# Asam & Basa\n\n$pH = -\\log[H^+]$. Larutan asam memiliki $pH < 7$, basa $pH > 7$.",
        ),
    ],
    "Biologi": [
        _lesson(
            "Sel sebagai Unit Kehidupan",
            "# Sel\n\n"
            "Sel adalah unit struktural dan fungsional terkecil makhluk hidup. "
            "Organel utama: nukleus, mitokondria, ribosom.",
        ),
        _lesson(
            "Fotosintesis",
            "# Fotosintesis\n\n6CO₂ + 6H₂O + cahaya → C₆H₁₂O₆ + 6O₂, berlangsung di kloroplas.",
        ),
        _lesson(
            "Sistem Peredaran Darah",
            "# Peredaran Darah\n\n"
            "Jantung memompa darah melalui arteri, kapiler, dan vena. Darah "
            "mengangkut oksigen dan sari makanan.",
        ),
        _lesson(
            "Genetika & Pewarisan Sifat",
            "# Genetika\n\n"
            "Hukum Mendel menjelaskan pewarisan sifat melalui gen. Persilangan "
            "monohibrid menghasilkan rasio 3:1 pada F₂.",
        ),
    ],
    "B. Indonesia": [
        _lesson(
            "Teks Eksposisi",
            "# Teks Eksposisi\n\n"
            "Struktur: tesis, argumentasi, penegasan ulang. Bersifat faktual dan "
            "bertujuan meyakinkan pembaca.",
        ),
        _lesson(
            "Teks Cerpen",
            "# Cerpen\n\n"
            "Unsur intrinsik: tema, tokoh, alur, latar, amanat. Cerpen fokus pada "
            "satu peristiwa utama.",
        ),
        _lesson(
            "Karya Ilmiah",
            "# Karya Ilmiah\n\n"
            "Sistematika: pendahuluan, landasan teori, metode, hasil, pembahasan, "
            "simpulan. Wajib objektif dan memakai bahasa baku.",
        ),
        _lesson(
            "Puisi & Majas",
            "# Puisi\n\nMajas memperkuat citraan puisi: personifikasi, metafora, hiperbola.",
        ),
    ],
    "B. Inggris": [
        _lesson(
            "Descriptive Text",
            "# Descriptive Text\n\n"
            "Purpose: to describe a particular person, place, or thing using "
            "simple present tense.",
        ),
        _lesson(
            "Narrative Text",
            "# Narrative Text\n\n"
            "Orientation → complication → resolution. Uses past tense and time "
            "connectives.",
        ),
        _lesson(
            "Procedure Text",
            "# Procedure Text\n\nGoal → materials → steps, written with imperative sentences.",
        ),
        _lesson(
            "Report Text",
            "# Report Text\n\nDescribes things in general (facts) rather than a single subject.",
        ),
    ],
    "Sejarah": [
        _lesson(
            "Proklamasi Kemerdekaan",
            "# Proklamasi\n\n"
            "Diproklamasikan 17 Agustus 1945 oleh Soekarno-Hatta di Jalan "
            "Pegangsaan Timur 56, Jakarta.",
        ),
        _lesson(
            "Masa Pergerakan Nasional",
            "# Pergerakan Nasional\n\n"
            "Ditandai berdirinya Budi Utomo (1908) dan Sumpah Pemuda (1928).",
        ),
        _lesson(
            "Orde Baru & Reformasi",
            "# Reformasi\n\n"
            "Reformasi 1998 menandai berakhirnya Orde Baru dan dimulainya era "
            "demokratisasi.",
        ),
    ],
    "Ekonomi": [
        _lesson(
            "Kebutuhan & Kelangkaan",
            "# Kebutuhan\n\n"
            "Kelangkaan muncul karena kebutuhan manusia tidak terbatas sedangkan "
            "sumber daya terbatas.",
        ),
        _lesson(
            "Permintaan & Penawaran",
            "# Pasar\n\n"
            "Hukum permintaan: harga naik, permintaan turun. Keseimbangan pasar "
            "terjadi saat $Q_d = Q_s$.",
        ),
        _lesson(
            "Uang & Perbankan",
            "# Uang & Bank\n\n"
            "Uang berfungsi sebagai alat tukar, satuan hitung, dan penyimpan "
            "nilai. Bank sentral mengatur kebijakan moneter.",
        ),
        _lesson(
            "Pendapatan Nasional",
            "# Pendapatan Nasional\n\n"
            "PDB mengukur nilai barang/jasa akhir yang diproduksi suatu negara "
            "dalam satu periode.",
        ),
    ],
    "Sosiologi": [
        _lesson(
            "Interaksi Sosial",
            "# Interaksi Sosial\n\n"
            "Bentuk: kerja sama, akomodasi, asimilasi, kompetisi, konflik. "
            "Faktor: imitasi, sugesti, identifikasi, simpati.",
        ),
        _lesson(
            "Nilai & Norma Sosial",
            "# Nilai & Norma\n\n"
            "Norma dibedakan menjadi cara, kebiasaan, tata kelakuan, dan adat "
            "istiadat berdasarkan daya ikatnya.",
        ),
        _lesson(
            "Perubahan Sosial",
            "# Perubahan Sosial\n\n"
            "Dipicu faktor internal (penemuan) dan eksternal (difusi budaya). "
            "Dapat bersifat evolusi atau revolusi.",
        ),
    ],
    "Geografi": [
        _lesson(
            "Konsep Dasar Geografi",
            "# Konsep Geografi\n\n"
            "Sepuluh konsep: lokasi, jarak, keterjangkauan, pola, morfologi, "
            "aglomerasi, nilai guna, interaksi, diferensiasi, keterkaitan ruang.",
        ),
        _lesson(
            "Litosfer & Vulkanisme",
            "# Litosfer\n\n"
            "Lempeng tektonik bergerak memicu gempa dan gunung berapi. Indonesia "
            "berada pada Cincin Api Pasifik.",
        ),
        _lesson(
            "Dinamika Atmosfer",
            "# Atmosfer\n\n"
            "Lapisan atmosfer: troposfer, stratosfer, mesosfer, termosfer. Cuaca "
            "dan iklim dipengaruhi suhu, tekanan, dan kelembapan.",
        ),
    ],
}


# ---------------------------------------------------------------------------
# Exam bank, keyed by subject. Each exam is a titled set of MC questions.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MCQuestion:
    prompt: str
    choices: tuple[str, ...]
    correct_index: int
    explanation: str


@dataclass(frozen=True)
class ExamSpec:
    title: str
    duration_minutes: int
    passing_score_bp: int
    instructions: str
    questions: list[MCQuestion] = field(default_factory=list)


def _mc(prompt: str, choices: list[str], correct: int, explanation: str) -> MCQuestion:
    return MCQuestion(
        prompt=prompt, choices=tuple(choices), correct_index=correct, explanation=explanation
    )


EXAM_BANK: dict[str, ExamSpec] = {
    "Matematika": ExamSpec(
        title="Ujian Matematika — Eksponen & Barisan",
        duration_minutes=45,
        passing_score_bp=7000,
        instructions="Pilih satu jawaban yang paling tepat. Kalkulator tidak diperlukan.",
        questions=[
            _mc(
                "Nilai dari 2³ × 2⁴ adalah …",
                ["64", "128", "256", "512"],
                1,
                "2³ × 2⁴ = 2⁷ = 128.",
            ),
            _mc(
                "Jika U₁ = 3 dan beda b = 4, suku ke-6 barisan aritmetika adalah …",
                ["19", "23", "27", "31"],
                1,
                "U₆ = 3 + 5·4 = 23.",
            ),
            _mc(
                "Akar-akar persamaan x² − 5x + 6 = 0 adalah …",
                ["1 dan 6", "2 dan 3", "-1 dan -6", "2 dan -3"],
                1,
                "x² − 5x + 6 = (x−2)(x−3).",
            ),
            _mc(
                "Median dari data 4, 7, 9, 10, 12 adalah …",
                ["7", "9", "10", "8.4"],
                1,
                "Data terurut: median = 9.",
            ),
            _mc(
                "Titik puncak f(x) = x² − 4x + 3 berada pada x = …",
                ["-2", "2", "3", "4"],
                1,
                "x_p = -b/2a = 4/2 = 2.",
            ),
        ],
    ),
    "Fisika": ExamSpec(
        title="Ujian Fisika — Kinematika & Dinamika",
        duration_minutes=50,
        passing_score_bp=7000,
        instructions="Tulis besaran, satuan, dan arah bila perlu.",
        questions=[
            _mc(
                "Mobil bergerak 72 km/jam. Kecepatan itu setara …",
                ["10 m/s", "20 m/s", "30 m/s", "40 m/s"],
                1,
                "72 km/jam = 72000/3600 = 20 m/s.",
            ),
            _mc(
                "Benda 2 kg didorong gaya 10 N. Percepatannya …",
                ["2 m/s²", "5 m/s²", "10 m/s²", "20 m/s²"],
                1,
                "a = F/m = 10/2 = 5 m/s².",
            ),
            _mc(
                "Usaha untuk memindahkan benda 5 m dengan gaya 20 N searah adalah …",
                ["4 J", "25 J", "100 J", "400 J"],
                2,
                "W = F·s = 20·5 = 100 J.",
            ),
            _mc(
                "Simbol gelombang: cepat rambat memenuhi …",
                ["v = λ/f", "v = λ·f", "v = f/λ", "v = λ + f"],
                1,
                "v = λ·f.",
            ),
        ],
    ),
    "Kimia": ExamSpec(
        title="Ujian Kimia — Atom & Stoikiometri",
        duration_minutes=45,
        passing_score_bp=7000,
        instructions="Gunakan tabel periodik bila diperlukan.",
        questions=[
            _mc(
                "Partikel penyusun atom yang bermuatan negatif adalah …",
                ["Proton", "Neutron", "Elektron", "Nukleon"],
                2,
                "Elektron bermuatan negatif.",
            ),
            _mc(
                "Jumlah mol dari 36 gram air (Mr = 18) adalah …",
                ["1 mol", "2 mol", "3 mol", "0,5 mol"],
                1,
                "n = 36/18 = 2 mol.",
            ),
            _mc(
                "Larutan dengan pH = 3 bersifat …",
                ["Basa kuat", "Asam", "Netral", "Basa lemah"],
                1,
                "pH < 7 berarti asam.",
            ),
        ],
    ),
    "Biologi": ExamSpec(
        title="Ujian Biologi — Sel & Genetika",
        duration_minutes=45,
        passing_score_bp=7000,
        instructions="Pilih jawaban yang paling tepat.",
        questions=[
            _mc(
                "Organel tempat fotosintesis berlangsung adalah …",
                ["Mitokondria", "Kloroplas", "Ribosom", "Nukleus"],
                1,
                "Fotosintesis terjadi di kloroplas.",
            ),
            _mc(
                "Hasil persilangan monohibrid F₂ genotipe heterozigot adalah …",
                ["25%", "50%", "75%", "100%"],
                1,
                "Rasio 1:2:1 → heterozigot 50%.",
            ),
            _mc(
                "Bagian darah yang mengangkut oksigen adalah …",
                ["Plasma", "Trombosit", "Eritrosit", "Leukosit"],
                2,
                "Eritrosit (sel darah merah) mengangkut O₂.",
            ),
        ],
    ),
    "B. Indonesia": ExamSpec(
        title="Ujian Bahasa Indonesia — Teks & Sastra",
        duration_minutes=40,
        passing_score_bp=7000,
        instructions="Pilih satu jawaban yang paling tepat.",
        questions=[
            _mc(
                "Struktur teks eksposisi adalah …",
                [
                    "Orientasi–komplikasi–resolusi",
                    "Tesis–argumentasi–penegasan ulang",
                    "Pembuka–isi–penutup",
                    "Tujuan–langkah",
                ],
                1,
                "Teks eksposisi: tesis, argumentasi, penegasan ulang.",
            ),
            _mc(
                "Majas 'angin berbisik' termasuk …",
                ["Metafora", "Personifikasi", "Hiperbola", "Litotes"],
                1,
                "Angin diberi sifat manusia → personifikasi.",
            ),
        ],
    ),
    "B. Inggris": ExamSpec(
        title="English Test — Descriptive & Narrative",
        duration_minutes=40,
        passing_score_bp=7000,
        instructions="Choose the best answer.",
        questions=[
            _mc(
                "The purpose of a descriptive text is to …",
                ["Tell a story", "Describe something", "Give instructions", "Report facts"],
                1,
                "Descriptive text describes a particular thing.",
            ),
            _mc(
                "The structure of a narrative text is …",
                [
                    "Goal – Materials – Steps",
                    "Orientation – Complication – Resolution",
                    "Thesis – Arguments",
                    "General – Facts",
                ],
                1,
                "Narrative: orientation, complication, resolution.",
            ),
        ],
    ),
    "Sejarah": ExamSpec(
        title="Ujian Sejarah — Kemerdekaan & Pergerakan",
        duration_minutes=40,
        passing_score_bp=7000,
        instructions="Pilih jawaban yang paling tepat.",
        questions=[
            _mc(
                "Proklamasi kemerdekaan dibacakan pada tanggal …",
                ["17 Agustus 1945", "1 Juni 1945", "28 Oktober 1928", "10 November 1945"],
                0,
                "Proklamasi: 17 Agustus 1945.",
            ),
            _mc(
                "Organisasi pergerakan nasional pertama adalah …",
                ["Sarekat Islam", "Budi Utomo", "PNI", "Partai Indonesia"],
                1,
                "Budi Utomo berdiri 1908.",
            ),
        ],
    ),
    "Ekonomi": ExamSpec(
        title="Ujian Ekonomi — Pasar & Kebijakan",
        duration_minutes=40,
        passing_score_bp=7000,
        instructions="Pilih jawaban yang paling tepat.",
        questions=[
            _mc(
                "Menurut hukum permintaan, ketika harga naik maka …",
                ["Permintaan naik", "Permintaan turun", "Permintaan tetap", "Penawaran turun"],
                1,
                "Harga naik → jumlah diminta turun.",
            ),
            _mc(
                "Keseimbangan pasar terjadi ketika …",
                ["Qd > Qs", "Qd < Qs", "Qd = Qs", "Qd = 0"],
                2,
                "Keseimbangan saat Qd = Qs.",
            ),
        ],
    ),
    "Sosiologi": ExamSpec(
        title="Ujian Sosiologi — Interaksi & Perubahan",
        duration_minutes=40,
        passing_score_bp=7000,
        instructions="Pilih jawaban yang paling tepat.",
        questions=[
            _mc(
                "Bentuk interaksi sosial yang mengarah pada penyatuan disebut …",
                ["Konflik", "Kompetisi", "Asimilasi", "Kontravensi"],
                2,
                "Asimilasi menyatukan budaya.",
            ),
            _mc(
                "Faktor eksternal perubahan sosial adalah …",
                ["Penemuan baru", "Difusi budaya", "Konflik internal", "Perubahan populasi"],
                1,
                "Difusi budaya datang dari luar masyarakat.",
            ),
        ],
    ),
    "Geografi": ExamSpec(
        title="Ujian Geografi — Litosfer & Atmosfer",
        duration_minutes=40,
        passing_score_bp=7000,
        instructions="Pilih jawaban yang paling tepat.",
        questions=[
            _mc(
                "Lapisan atmosfer tempat terjadinya cuaca adalah …",
                ["Stratosfer", "Troposfer", "Mesosfer", "Termosfer"],
                1,
                "Cuaca terjadi di troposfer.",
            ),
            _mc(
                "Indonesia terletak pada jalur … yang rawan gempa.",
                ["Cincin Api Pasifik", "Gurun Sahara", "Palung Mariana", "Lempeng Eurasia"],
                0,
                "Indonesia berada di Cincin Api Pasifik.",
            ),
        ],
    ),
}


# ---------------------------------------------------------------------------
# Community feed seed material (topics come from the community service).
# ---------------------------------------------------------------------------
# Topics match ``community_service.TOPICS`` so the feed groups cleanly.
COMMUNITY_POSTS: list[tuple[str, str]] = [
    ("Umum", "Selamat pagi! Semangat belajar hari ini, jangan lupa istirahat cukup."),
    ("Umum", "Ruang belajar malam ini jam 19.00, kita bahas soal latihan bersama."),
    ("Umum", "Terima kasih untuk para guru yang sudah menyiapkan materi dengan rapi."),
    ("Tanya Jawab", "Ada yang paham cara cepat mencari akar persamaan kuadrat tanpa rumus abc?"),
    ("Tanya Jawab", "Materi listrik dinamis pekan ini menantang, ada tips memahami hukum Ohm?"),
    ("Tanya Jawab", "Diskusi soal barisan aritmetika tipe SNBT, siapa mau ikut latihan bareng?"),
    ("Data & AI", "Baru selesai kuis pilihan ganda, dapat badge Quiz Master! Semangat semua."),
    ("Data & AI", "Menarik, AI di QLoot bisa membantu latihan essay. Sudah coba?"),
    ("Karier & Portofolio", "Aku tertarik teknik elektro, kira-kira jurusan SMA-nya harus IPA ya?"),
    (
        "Karier & Portofolio",
        "Sharing: konsultasi BK sangat membantu memilih jurusan. Jangan ragu ke BK!",
    ),
    ("Karier & Portofolio", "Rekomendasi kampus untuk Ilmu Komputer selain ITB dan UI apa ya?"),
    ("Web3 & Blockchain", "Sertifikat digitalku bisa diverifikasi lewat tautan unik, keren!"),
    ("Desain & UX", "Tips menyusun portofolio: mulai dari masalah, bukan dari visual."),
    ("Desain & UX", "Rangkuman rumus eksponen dan bentuk akar kelas 10 sudah aku unggah ya!"),
    ("Tanya Jawab", "Strategi ujian: kerjakan soal yang mudah dulu, jangan terjebak satu nomor."),
]

COMMUNITY_COMMENTS: list[str] = [
    "Setuju, terima kasih sudah berbagi!",
    "Boleh minta link materinya?",
    "Aku juga sedang belajar bagian ini, semangat!",
    "Penjelasannya membantu banget.",
    "Nanti kita diskusikan di ruang belajar ya.",
    "Wah, aku baru tahu. Makasih tips-nya!",
    "Kira-kira ada contoh soal serupa tidak?",
    "Catatanku berbeda, tapi punyamu lebih ringkas.",
]


# ---------------------------------------------------------------------------
# Career resources (rekomendasi jurusan & aktivitas). Real, specific entries.
# ---------------------------------------------------------------------------
CAREER_RESOURCES: list[ResourceSpec] = [
    {
        "code": "res-mat-olim",
        "category": "course",
        "title": "Olimpiade Matematika SMA",
        "description": "Pembinaan intensif aljabar, kombinatorika, dan geometri untuk OSN.",
        "provider": "Puspresnas",
        "is_free": True,
        "tags": ["Matematika", "Olimpiade"],
    },
    {
        "code": "res-fis-lab",
        "category": "extracurricular",
        "title": "Klub Fisika & Robotik",
        "description": "Eksperimen kinematika, listrik, dan perakitan robot line-follower.",
        "provider": "QLoot Labs",
        "is_free": True,
        "tags": ["Fisika", "Robotik"],
    },
    {
        "code": "res-kim-praktikum",
        "category": "material",
        "title": "Modul Praktikum Kimia Dasar",
        "description": "Panduan titrasi asam-basa dan stoikiometri larutan.",
        "provider": "QLoot Academy",
        "is_free": True,
        "tags": ["Kimia"],
    },
    {
        "code": "res-bio-genetik",
        "category": "course",
        "title": "Genetika untuk Pemula",
        "description": "Hukum Mendel, persilangan, dan dasar bioteknologi.",
        "provider": "QLoot Academy",
        "is_free": True,
        "tags": ["Biologi"],
    },
    {
        "code": "res-eng-toefl",
        "category": "course",
        "title": "Persiapan TOEFL ITP",
        "description": "Latihan listening, structure, dan reading comprehension.",
        "provider": "Language Center",
        "is_free": False,
        "tags": ["B. Inggris"],
    },
    {
        "code": "res-bind-ilmiah",
        "category": "material",
        "title": "Menulis Karya Ilmiah Remaja",
        "description": "Panduan menyusun laporan penelitian sesuai kaidah PUEBI.",
        "provider": "QLoot Academy",
        "is_free": True,
        "tags": ["B. Indonesia"],
    },
    {
        "code": "res-eko-akuntansi",
        "category": "extracurricular",
        "title": "Klub Ekonomi & Akuntansi",
        "description": "Simulasi pasar, literasi keuangan, dan dasar pembukuan.",
        "provider": "QLoot Academy",
        "is_free": True,
        "tags": ["Ekonomi"],
    },
    {
        "code": "res-sej-museum",
        "category": "extracurricular",
        "title": "Jelajah Sejarah & Museum",
        "description": "Kunjungan virtual museum perjuangan dan analisis sumber sejarah.",
        "provider": "Dinas Kebudayaan",
        "is_free": True,
        "tags": ["Sejarah"],
    },
    {
        "code": "res-geo-sig",
        "category": "course",
        "title": "Sistem Informasi Geografis (SIG)",
        "description": "Membaca peta, citra satelit, dan analisis spasial sederhana.",
        "provider": "QLoot Labs",
        "is_free": False,
        "tags": ["Geografi"],
    },
    {
        "code": "res-sos-riset",
        "category": "material",
        "title": "Metode Riset Sosial Sederhana",
        "description": "Menyusun angket, wawancara, dan laporan observasi sosial.",
        "provider": "QLoot Academy",
        "is_free": True,
        "tags": ["Sosiologi"],
    },
]

# Major catalogue for AI recommendations.
MAJORS: list[MajorSpec] = [
    {
        "major": "Teknik Informatika",
        "universities": ["ITB", "UI", "ITS", "UGM"],
        "admission_paths": ["SNBP", "SNBT", "Mandiri"],
        "skills": ["Logika", "Pemrograman", "Matematika Diskret"],
        "careers": ["Software Engineer", "Data Scientist", "AI Engineer"],
        "rationale_best_for": ["Matematika", "Fisika"],
    },
    {
        "major": "Kedokteran",
        "universities": ["UI", "UGM", "Unair", "Undip"],
        "admission_paths": ["SNBP", "SNBT"],
        "skills": ["Biologi", "Kimia", "Komunikasi"],
        "careers": ["Dokter", "Spesialis", "Peneliti Medis"],
        "rationale_best_for": ["Biologi", "Kimia"],
    },
    {
        "major": "Teknik Elektro",
        "universities": ["ITB", "ITS", "UGM"],
        "admission_paths": ["SNBP", "SNBT", "Mandiri"],
        "skills": ["Fisika", "Matematika", "Analisis Rangkaian"],
        "careers": ["Electrical Engineer", "IoT Developer", "Kontrol & Instrumentasi"],
        "rationale_best_for": ["Fisika", "Matematika"],
    },
    {
        "major": "Akuntansi",
        "universities": ["UI", "UGM", "Unpad", "Binus"],
        "admission_paths": ["SNBP", "SNBT", "Mandiri"],
        "skills": ["Ekonomi", "Ketelitian", "Analisis Data"],
        "careers": ["Akuntan Publik", "Auditor", "Analis Keuangan"],
        "rationale_best_for": ["Ekonomi", "Matematika"],
    },
    {
        "major": "Psikologi",
        "universities": ["UI", "UGM", "Unpad", "Unair"],
        "admission_paths": ["SNBP", "SNBT", "Mandiri"],
        "skills": ["Sosiologi", "Komunikasi", "Empati"],
        "careers": ["Psikolog Klinis", "HRD", "Konselor"],
        "rationale_best_for": ["Sosiologi", "B. Indonesia"],
    },
    {
        "major": "Ilmu Hukum",
        "universities": ["UI", "UGM", "Unpad", "Undip"],
        "admission_paths": ["SNBP", "SNBT", "Mandiri"],
        "skills": ["B. Indonesia", "Analisis", "Argumentasi"],
        "careers": ["Advokat", "Notaris", "Hakim", "Legal Officer"],
        "rationale_best_for": ["B. Indonesia", "Sejarah"],
    },
    {
        "major": "Teknik Sipil",
        "universities": ["ITB", "ITS", "UGM", "Undip"],
        "admission_paths": ["SNBP", "SNBT", "Mandiri"],
        "skills": ["Fisika", "Matematika", "Perencanaan"],
        "careers": ["Civil Engineer", "Kontraktor", "Konsultan Struktur"],
        "rationale_best_for": ["Fisika", "Matematika"],
    },
    {
        "major": "Manajemen",
        "universities": ["UI", "UGM", "Unpad", "Binus"],
        "admission_paths": ["SNBP", "SNBT", "Mandiri"],
        "skills": ["Ekonomi", "Kepemimpinan", "Analisis"],
        "careers": ["Business Analyst", "Manajer", "Entrepreneur"],
        "rationale_best_for": ["Ekonomi", "Sosiologi"],
    },
]

# Assistant-conversation prompts (career guidance). Realistic Q&A pairs.
ASSISTANT_TURNS: list[tuple[str, str]] = [
    (
        "Bedanya SNBP dan SNBT itu apa ya?",
        "SNBP (Seleksi Nasional Berdasarkan Prestasi) menilai rapor dan prestasi tanpa tes, "
        "sedangkan SNBT memakai hasil UTBK. Pilih SNBP bila nilai rapor konsisten baik, "
        "dan siapkan SNBT sebagai jalur utama kedua.",
    ),
    (
        "Prospek kerja Ilmu Komputer seperti apa?",
        "Lulusannya banyak dicari sebagai Software Engineer, Data Scientist, dan AI Engineer. "
        "Bekali diri dengan portofolio proyek dan penguasaan algoritma sejak SMA.",
    ),
    (
        "Jurusan yang cocok untuk anak IPA?",
        "Untuk peminat IPA: Kedokteran, Teknik (Informatika/Elektro/Sipil), atau sains murni. "
        "Pertimbangkan kekuatan mapelmu: Biologi-Kimia ke kesehatan, Fisika-Matematika ke teknik.",
    ),
    (
        "Bagaimana cara memperbaiki nilai rapor semester ini?",
        "Fokus pada mapel dengan bobot besar, ikuti ujian perbaikan bila tersedia, dan kumpulkan "
        "tugas tepat waktu. Diskusikan target dengan guru BK agar terarah.",
    ),
    (
        "Kapan sebaiknya mulai menyiapkan UTBK?",
        "Mulai kelas 11 semester genap. Latihan soal secara berkala (sedikit tapi konsisten) "
        "lebih efektif daripada sistem kebut semalam menjelang ujian.",
    ),
]


# ---------------------------------------------------------------------------
# Consultation topics (BK guidance) — realistic, varied.
# ---------------------------------------------------------------------------
CONSULTATION_TOPICS: list[str] = [
    "Konsultasi Pemilihan Jurusan Kuliah",
    "Strategi Menghadapi SNBT",
    "Perbaikan Nilai Rapor Semester Ini",
    "Pemetaan Minat & Bakat",
    "Persiapan Olimpiade Sains",
    "Manajemen Waktu Belajar & Ekstrakurikuler",
    "Rencana Studi Lanjut ke Luar Negeri",
]

COUNSELORS: list[str] = ["Bu Ratna Wijaya", "Pak Aditya Nugraha"]


# ---------------------------------------------------------------------------
# Task catalogue (mirror the app's task kinds).
# ---------------------------------------------------------------------------
TASK_BANK: list[tuple[str, str, str, int]] = [
    ("Menyelesaikan 1 Pelajaran", "Tuntaskan satu pelajaran hingga akhir.", "learning", 10),
    ("Membaca 1 Materi PDF", "Selesaikan membaca satu materi pembelajaran.", "learning", 10),
    ("Hadir di 1 Ruang Belajar", "Bergabung ke satu ruang belajar/kompetisi.", "daily", 5),
    ("Menuntaskan 1 Ujian", "Selesaikan satu ujian yang tersedia.", "exam", 20),
    ("Mengerjakan 1 Kuis", "Coba tes pilihan ganda cepat.", "daily", 5),
]


# ---------------------------------------------------------------------------
# Stable helper accessors (pure; no DB, no randomness).
# ---------------------------------------------------------------------------
def subjects() -> list[str]:
    """All subject names in a stable order."""
    return list(SUBJECT_LESSONS.keys())


def lessons_for(subject: str) -> list[LessonSpec]:
    return SUBJECT_LESSONS.get(subject, [])


def exam_for(subject: str) -> ExamSpec | None:
    return EXAM_BANK.get(subject)


def class_for(index: int) -> tuple[str, str]:
    """Deterministically pick a (class_code, class_type) for an index."""
    return CLASSES[index % len(CLASSES)]


def major_for(index: int) -> MajorSpec:
    return MAJORS[index % len(MAJORS)]


def resource_for(index: int) -> ResourceSpec:
    return CAREER_RESOURCES[index % len(CAREER_RESOURCES)]
