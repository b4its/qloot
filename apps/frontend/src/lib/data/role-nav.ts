/**
 * Single source of truth for in-section navigation of the teacher and admin
 * areas. The layout renders these as a per-role sub-nav so each role has its
 * own clean set of links, and the hub pages reuse the labels/icons.
 */

export interface RoleNavItem {
  href: string;
  label: string;
  icon: string;
  desc?: string;
}

export const teacherNav: RoleNavItem[] = [
  {
    href: "/teacher",
    label: "Ringkasan",
    icon: "gauge-high",
    desc: "Statistik kelas dan pintasan",
  },
  {
    href: "/teacher/subjects",
    label: "Pelajaran",
    icon: "chalkboard-user",
    desc: "Buat pelajaran, pilih kelas & tipe kelas",
  },
  {
    href: "/teacher/materials",
    label: "Materi",
    icon: "file-arrow-up",
    desc: "Unggah PDF dan buat soal dengan AI",
  },
  {
    href: "/teacher/exams",
    label: "Ujian",
    icon: "file-pen",
    desc: "Buat ujian, tinjau soal AI, publikasikan",
  },
  {
    href: "/teacher/quests",
    label: "Quest",
    icon: "trophy",
    desc: "Atur hadiah dan finalisasi pemenang",
  },
  {
    href: "/teacher/tasks",
    label: "Tugas",
    icon: "list-check",
    desc: "Buat dan atur tugas harian/mingguan",
  },
  {
    href: "/teacher/submissions",
    label: "Jawaban",
    icon: "inbox",
    desc: "Jawaban siswa, feedback, dan analitik",
  },
  {
    href: "/teacher/rankings",
    label: "Peringkat",
    icon: "ranking-star",
    desc: "Periksa papan peringkat",
  },
];

export const adminNav: RoleNavItem[] = [
  {
    href: "/admin",
    label: "Ringkasan",
    icon: "gauge-high",
    desc: "Pintasan operasional platform",
  },
  {
    href: "/admin/users",
    label: "Pengguna",
    icon: "users",
    desc: "Kelola peran dan akun",
  },
  {
    href: "/admin/rewards",
    label: "Hadiah",
    icon: "gem",
    desc: "Pantau, ulangi dan batalkan alokasi OPT",
  },
  {
    href: "/admin/withdrawals",
    label: "Penarikan",
    icon: "money-bill-transfer",
    desc: "Setujui atau tolak permintaan penarikan",
  },
  {
    href: "/admin/ledger",
    label: "Ledger",
    icon: "book",
    desc: "Rekonsiliasi saldo dan akun berutang",
  },
  {
    href: "/admin/blockchain",
    label: "Blockchain",
    icon: "cube",
    desc: "Status, transaksi, pause/unpause",
  },
  {
    href: "/admin/audit",
    label: "Audit Log",
    icon: "scroll",
    desc: "Setiap tindakan istimewa tercatat",
  },
];
