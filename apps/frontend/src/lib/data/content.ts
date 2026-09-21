/**
 * Static demo content for the public marketing pages (Bahasa Indonesia).
 *
 * QLoot is a class-based e-learning platform — there are no paid courses.
 * Content here describes the platform, not a storefront.
 */

export interface ClassTrack {
  code: string; // e.g. "1A"
  type: string; // e.g. "IPA"
  label: string; // e.g. "Kelas 1 IPA"
  subjects: string[];
  students: number;
  icon: string; // Font Awesome icon name
  accent: string; // gradient CSS
}

export interface Feature {
  icon: string;
  title: string;
  desc: string;
}

export interface Mentor {
  name: string;
  handle: string;
  role: string;
  subject: string;
}

export interface Testimonial {
  quote: string;
  name: string;
  role: string;
}

export const classTracks: ClassTrack[] = [
  {
    code: "1A",
    type: "IPA",
    label: "Kelas 1 · IPA",
    subjects: ["Matematika", "Bahasa Indonesia", "Fisika"],
    students: 32,
    icon: "flask-vial",
    accent: "linear-gradient(135deg,#FCEE0A,#FF6B2C)",
  },
  {
    code: "2D",
    type: "IPS",
    label: "Kelas 2 · IPS",
    subjects: ["Ekonomi", "Sosiologi", "Sejarah"],
    students: 30,
    icon: "earth-asia",
    accent: "linear-gradient(135deg,#00F0FF,#FCEE0A)",
  },
  {
    code: "3A",
    type: "IPA",
    label: "Kelas 3 · IPA",
    subjects: ["Fisika", "Kimia", "Biologi"],
    students: 28,
    icon: "atom",
    accent: "linear-gradient(135deg,#FF2E88,#FCEE0A)",
  },
  {
    code: "3B",
    type: "IPS",
    label: "Kelas 3 · IPS",
    subjects: ["Ekonomi", "Geografi", "Sosiologi"],
    students: 29,
    icon: "chart-pie",
    accent: "linear-gradient(135deg,#FF6B2C,#00F0FF)",
  },
];

export const features: Feature[] = [
  {
    icon: "chalkboard-user",
    title: "Pelajaran per Kelas",
    desc: "Guru membuat pelajaran dan menargetkan kelasnya (mis. 1A, 2D). Siswa hanya melihat pelajaran sesuai kelasnya.",
  },
  {
    icon: "file-arrow-up",
    title: "Materi & Modul",
    desc: "Unggah PDF sebagai sumber materi; AI membantu merangkum dan menyusun soal latihan.",
  },
  {
    icon: "brain",
    title: "Penilaian AI",
    desc: "Jawaban esai dinilai otomatis dengan umpan balik dan skor kemiripan yang transparan.",
  },
  {
    icon: "gamepad",
    title: "Quest & Ruang",
    desc: "Kompetisi kelas real-time, ranking, dan quest berhadiah untuk menjaga motivasi belajar.",
  },
  {
    icon: "gem",
    title: "Hadiah OPC",
    desc: "Setiap pencapaian tercatat sebagai OryphemCoin (OPC) — reward digital yang dapat dilacak.",
  },
  {
    icon: "certificate",
    title: "Sertifikat Digital",
    desc: "Kredensial dengan ID unik dan tautan verifikasi untuk portofolio belajar siswa.",
  },
];

export const mentors: Mentor[] = [
  { name: "Budi Santoso", handle: "0xb1d4", role: "Guru Matematika", subject: "Matematika" },
  { name: "Sari Melati", handle: "0x9c2b", role: "Guru Ekonomi", subject: "Ekonomi" },
  { name: "Rangga Wibisono", handle: "0x7a2f", role: "Guru Fisika", subject: "Fisika" },
  { name: "Nadia Kusuma", handle: "0x4d18", role: "Guru Bahasa", subject: "Bahasa Indonesia" },
  { name: "Citra Halim", handle: "0x2e60", role: "Guru Sosiologi", subject: "Sosiologi" },
  { name: "Dimas Ardhana", handle: "0x8b93", role: "Guru Kimia", subject: "Kimia" },
];

export const testimonials: Testimonial[] = [
  {
    quote:
      "Saya tidak perlu mencari materi lagi. Semua pelajaran kelas 1A sudah tersusun rapi dan bisa langsung dibuka.",
    name: "Refa Anjani",
    role: "Siswa Kelas 1A",
  },
  {
    quote:
      "Sebagai guru, menargetkan pelajaran ke kelas tertentu sangat memudahkan. Siswa yang salah kelas tidak akan melihatnya.",
    name: "Budi Santoso",
    role: "Guru Matematika",
  },
  {
    quote:
      "Quest dan ranking membuat anak-anak lebih semangat belajar. Hadiah OPC jadi pemacu tambahan.",
    name: "Sari Melati",
    role: "Guru Ekonomi",
  },
];
