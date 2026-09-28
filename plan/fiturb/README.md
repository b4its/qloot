# Fiturb: Blue Cyberpunk Web3 Learning

`plan/fiturb/` adalah paket audit dan rencana implementasi QLoot berdasarkan kondisi
repository pada **28 September 2026**. Fokusnya bukan menambah daftar fitur secara acak,
melainkan menyatukan fitur yang sudah luas menjadi pengalaman pembelajaran teacher-student
yang koheren, aman, dan terukur dengan identitas visual **Cyberpunk 2077 blue-first**.

## Dokumen

| Dokumen | Kegunaan |
|---|---|
| [`00-AUDIT-REPOSITORY.md`](00-AUDIT-REPOSITORY.md) | Inventaris folder, arsitektur, status fitur, risiko, dan temuan lintas kode |
| [`01-DESIGN-SYSTEM-BLUE-CYBERPUNK.md`](01-DESIGN-SYSTEM-BLUE-CYBERPUNK.md) | Token warna, komponen, motion, responsive, accessibility, dan aturan visual |
| [`02-MATRIKS-FITUR-DAN-JOURNEY.md`](02-MATRIKS-FITUR-DAN-JOURNEY.md) | Matriks role, alur teacher-student-Web3, state, API, dan acceptance criteria |
| [`03-ROADMAP-EKSEKUSI.md`](03-ROADMAP-EKSEKUSI.md) | Wave P0-P2, dependensi, target commit atomik, dan definition of done |
| [`04-QUALITY-GATES.md`](04-QUALITY-GATES.md) | Strategi test backend/frontend/contract/E2E, keamanan, performa, dan rilis |
| [`PROMPT-IMPLEMENTASI.md`](PROMPT-IMPLEMENTASI.md) | Prompt utama dan prompt per-wave yang siap dipakai implementor |

## Urutan Baca

1. Baca audit dan daftar risiko P0 di `00-AUDIT-REPOSITORY.md`.
2. Setujui kontrak visual di `01-DESIGN-SYSTEM-BLUE-CYBERPUNK.md` sebelum mengubah halaman.
3. Pilih journey di `02-MATRIKS-FITUR-DAN-JOURNEY.md`, bukan halaman secara acak.
4. Eksekusi wave sesuai urutan di `03-ROADMAP-EKSEKUSI.md`.
5. Gunakan gate di `04-QUALITY-GATES.md` sebelum setiap commit dan sebelum rilis.
6. Gunakan prompt di `PROMPT-IMPLEMENTASI.md` untuk sesi implementasi yang terisolasi.

## Prinsip Utama

- **Learning-first:** token, XP, badge, quest, room, dan ranking harus memperkuat aktivitas
  belajar nyata, bukan menjadi permainan klik atau spekulasi.
- **Blue-first:** biru elektrik adalah aksi dan progres; cyan adalah data/AI/Web3; kuning
  menjadi warna OPT, legendary reward, dan hazard, bukan primary action global.
- **Full vertical slice:** fitur selesai hanya bila model/service/API/UI/state/error/test/docs
  lengkap dan dapat digunakan tanpa `curl`.
- **Simulation-first:** `AI_PROVIDER=mock` dan `BLOCKCHAIN_DRY_RUN=true` tetap menjadi jalur
  demo/test deterministik tanpa API key, RPC, atau dana nyata.
- **Financial correctness first:** perubahan reward, wallet, withdrawal, swap, dan chain harus
  idempoten, dapat direkonsiliasi, dan punya kompensasi kegagalan.
- **Atomic delivery:** satu commit adalah satu perubahan perilaku yang bisa diuji dan di-revert.

## Batasan Tema

Yang dimaksud “menyerupai Cyberpunk 2077” adalah bahasa visual generik: HUD, data slab,
clipped corner, neon edge, scanline ringan, high-contrast telemetry, dan motion singkat.
Jangan memakai logo, artwork, karakter, nama lokasi, atau aset hak cipta milik CD Projekt.
