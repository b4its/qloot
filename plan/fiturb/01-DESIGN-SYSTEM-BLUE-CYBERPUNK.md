# Design System Blue Cyberpunk

## 1. Arah Visual

Bahasa visual: **learning command center** yang terinspirasi HUD cyberpunk, bukan dashboard
SaaS generik dan bukan replika aset game tertentu.

- Angular data slab, clipped corners, thin neon edge.
- Dense telemetry hanya untuk informasi yang bernilai; ruang napas tetap cukup.
- Hierarki kuat: mission → progress → action → reward.
- Blue sebagai aksi/progres; cyan sebagai data/AI/chain; yellow sebagai reward/hazard.
- Light dan dark adalah dua cycle yang dirancang, bukan invert otomatis.

## 2. Token Warna

### Semantic Palette

| Token | Dark | Light | Fungsi |
|---|---|---|---|
| `--bg` | `#040812` | `#EAF2FF` | Canvas |
| `--surface` | `#081426` | `#F7FAFF` | Card/panel |
| `--elevated` | `#0D2038` | `#FFFFFF` | Dialog/popover |
| `--ink` | `#E8F4FF` | `#071426` | Primary text |
| `--ink2` | `#A9C5DE` | `#2D4A66` | Secondary text |
| `--muted` | `#708DA8` | `#58718A` | Metadata |
| `--line` | `#173A5E` | `#B8CDE3` | Border/grid |
| `--accent` | `#168BFF` | `#0066D6` | Primary action/focus |
| `--neon-blue` | `#168BFF` | `#0066D6` | Selection/action glow |
| `--neon-cyan` | `#00E5FF` | `#007F91` | AI/data/Web3 signal |
| `--neon-yellow` | `#FCEE0A` | `#8A7600` | OPT/legendary/hazard |
| `--neon-magenta` | `#FF3D9A` | `#B81768` | Social/rare |
| `--neon-red` | `#FF315B` | `#C91843` | Destructive/critical |

### Semantic Rules

- Primary button, active nav, focus, selected chip: blue.
- AI generation, streaming, RAG source, chain telemetry: cyan.
- OPT balance/reward/legendary badge: yellow.
- Warning/pending settlement: amber/yellow dengan teks eksplisit.
- Destructive action/error: red; jangan gunakan magenta sebagai error.
- Rare/social accent: magenta, maksimal satu focal point per section.
- Status tidak boleh disampaikan hanya lewat warna; selalu ada icon/text.

## 3. Typography

- Display/headings: `Chakra Petch`, tegas dan angular.
- Body/forms: `Rajdhani`, minimal 16px pada field mobile.
- Telemetry/code/address: `JetBrains Mono`, jangan dipakai untuk paragraf panjang.
- Heading maksimum 2 jenis emphasis sekaligus; hindari glitch pada konten akademik.

## 4. Components

### Buttons

- `btn-primary`: gradient blue → cyan, dark readable text hanya bila contrast terpenuhi;
  bila cyan terlalu terang gunakan navy text.
- `btn-secondary`: transparent blue edge.
- `btn-ghost`: hover blue wash.
- Yellow button khusus reward claim/OPT, tidak menjadi default CTA.
- Semua state: default, hover, active, focus-visible, disabled, busy.

### Cards

- Angular card tetap dipertahankan.
- Corner accent menjadi blue/cyan.
- Hover glow hanya untuk card interaktif; metric card statis tidak perlu lift.
- Hindari nested card berulang; gunakan divider/data-rule untuk hierarchy.

### Search, Filter, Sort

- Gunakan `SearchInput`, `FilterChips`, dan select berlabel.
- Clear search harus punya nama aksesibel.
- Filter mutually exclusive: button group + `aria-pressed` atau true tabs bila mengganti panel.
- Filter change reset pagination.
- Tampilkan active-filter summary dan reset hanya ketika filter aktif.

### Metric Strip

- Gunakan `MetricStrip`; 2 kolom mobile, maksimum 4 desktop.
- Label pendek, nilai menonjol, satu optional supporting text.
- Jangan gunakan warna dekoratif tanpa makna.

### Progress

- Semua bar: `role="progressbar"`, `aria-valuenow/min/max`, dan accessible label.
- Siswa melihat numerator/denominator selain persen.
- Reward settlement memakai stepper: `dialokasikan → submitted → confirmed`.

### Empty, Error, Loading

- `Skeleton` untuk loading, bentuk mendekati konten akhir.
- `EmptyState` membedakan belum ada data vs hasil filter kosong.
- Error state menyediakan retry bila request dapat diulang.
- Partial failure tidak menghapus data section lain.

### Wallet dan Web3

- Selalu bedakan `Saldo tersedia`, `Pending chain`, dan `Saldo aset`.
- Tampilkan network, contract, tx hash pendek, confirmation, explorer link.
- Jelaskan custodial treasury vs wallet pribadi.
- Jangan menampilkan “berhasil” sebelum indexer confirmed.
- Withdrawal menampilkan destination, amount, fee, review state, tx state, dan cancel eligibility.

## 5. Layout per Role

### Student

- Dashboard sebagai mission control: next lesson, deadline, active mission, progress, reward.
- Navigation groups: Belajar, Kompetisi, Komunitas, Karier, Aset/Akun.
- Mobile bottom nav maksimum 5 destination; sisanya melalui grouped launcher.

### Teacher

- Dashboard: pending review, grading queue, upcoming exam, quest close, at-risk students.
- Navigation groups: Konten, Penilaian, Engagement, Siswa, Karier.
- Authoring flow menggunakan visible stepper dan draft status.

### Admin

- Dashboard: system health, financial integrity, trust/safety, action queue.
- Navigation groups: People, Economy, Trust, Blockchain, Platform.
- Critical operation selalu melalui confirm dialog + reason + audit trace.

## 6. Motion

- 120-220ms untuk interaction, 400-600ms untuk page reveal.
- Scanline/sweep/glitch tidak boleh menutupi field, hasil ujian, atau dialog.
- Reduced motion mematikan transform, shimmer, marquee, scan, glow pulse.
- Loading streaming assistant boleh menggunakan typing dots; jangan memalsukan progress AI.

## 7. Responsive

### Mobile `<640px`

- Target tap minimum 44x44 px.
- Filter chips boleh horizontal scroll dengan visible affordance atau wrap terkontrol.
- Table berubah menjadi stacked row/card bila kolom tidak esensial.
- Exam navigation tetap reachable tanpa menutup jawaban.
- Safe-area bottom diperhitungkan.

### Tablet `640-1024px`

- Sidebar dapat collapse; metric strip 2-4 kolom sesuai ruang.
- Authoring menggunakan split view hanya bila field minimum width terpenuhi.

### Desktop `>1024px`

- Max content width menjaga scanability.
- Sticky context/action rail untuk workflow panjang.
- Jangan memperlebar paragraf lebih dari sekitar 70 karakter.

## 8. Accessibility Acceptance

- WCAG 2.2 AA untuk text, focus, keyboard, target size, dialog, status announcement.
- Semua icon-only button punya label.
- Dialog trap focus dan restore opener.
- Skip link tersedia pada semua shell.
- Toast/async success memakai `role=status`; error memakai `role=alert`.
- Unread/live indicator memiliki nama dan bukan dot warna semata.
- Theme blue light/dark diuji contrast-nya, bukan hanya screenshot.

## 9. Migration Strategy

1. Tambahkan token `--neon-blue`; ubah `--accent` dan Tailwind `primary` ke blue.
2. Ubah hardcoded yellow pada primary button, focus, selection, scrollbar, nav, skeleton,
   card corner, and signature gradients menjadi variable semantic.
3. Pertahankan yellow pada OPT, reward, legendary, hazard stripe, dan warning.
4. Tambahkan alias `reward`, `data`, `critical` agar page tidak memakai raw hex.
5. Jalankan contrast audit light/dark.
6. Buat screenshot baseline halaman landing/dashboard/exam/teacher/admin/wallet.
7. Migrasikan halaman per journey, bukan per warna.

## 10. Visual Acceptance Checklist

- [ ] Primary CTA blue pada light dan dark.
- [ ] OPT/reward tetap recognizable yellow.
- [ ] Focus ring terlihat jelas di semua surface.
- [ ] Card geometry konsisten dan tidak memotong konten.
- [ ] Hover tidak menjadi satu-satunya affordance.
- [ ] Mobile tidak horizontal overflow, kecuali control yang sengaja scrollable.
- [ ] Reduced motion tidak menyisakan animation berulang.
- [ ] Screenshot regression disetujui untuk lima halaman kunci.
