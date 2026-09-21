# QLoot

**QLoot** is a gamified, class-based e-learning platform with **AI-assisted exams**,
**competitive real-time rooms**, **quests & rankings**, and **blockchain rewards**
through the **OryphemCoin (OPC)** ERC-1155 token.

It is a ground-up reimplementation inspired by the domain of
[SayGenFix](https://github.com/mhaatha/saygenfix) (a Go/AI essay-exam app), rebuilt as
a **FastAPI + SvelteKit** monorepo with proper transactions, object-level RBAC,
background workers, and Web3 rewards.

> The whole platform runs as a **deterministic simulation** offline: the AI provider
> defaults to a mock, the chain client defaults to `dry_run`, and the career-guidance
> module is fully simulated — no external services or API keys are required to run,
> demo, or test the system.

---

## Table of contents

- [Ringkasan sistem](#ringkasan-sistem)
- [Fitur](#fitur)
- [Tech stack](#tech-stack)
- [Arsitektur](#arsitektur)
- [Instalasi](#instalasi)
- [Cara penggunaan](#cara-penggunaan)
- [Seed data](#seed-data)
- [Pengujian](#pengujian)
- [Blockchain lokal](#blockchain-lokal)
- [Struktur repositori](#struktur-repositori)
- [Keamanan](#keamanan)

---

## Ringkasan sistem

QLoot memodelkan sebuah sekolah digital:

- **Guru (teacher)** membuat *pelajaran* (subject) yang ditargetkan ke sebuah **kelas**
  (mis. `1A · IPA`), mengunggah **materi PDF**, membuat **ujian**, **quest**, **ruang**,
  dan **tugas**.
- **Siswa (student)** terdaftar pada satu kelas dan otomatis melihat pelajaran untuk
  kelasnya. Mereka mengerjakan ujian, mengumpulkan jawaban, dan mengikuti quest untuk
  memperoleh **OryphemCoin (OPC)**.
- **Admin** mengelola pengguna, hadiah, audit log, dan kontrol blockchain.

Setiap aktivitas bernilai (menyelesaikan quest, tugas, ujian sempurna, dsb.) menghasilkan
**reward OPC** yang dicatat pada **ledger double-entry**, diterbitkan sebagai event
*outbox* transaksional, lalu diproses oleh **blockchain worker** dan dikonfirmasi oleh
**indexer**.

---

## Fitur

- **Pembelajaran berbasis kelas** — pelajaran per kelas, materi, progres, dan PDF upload.
- **AI (simulasi)** — pembuatan soal dari PDF, penilaian esai, ringkasan materi, dan
  tanya-jawab berbasis materi; struktur output tervalidasi, retry, dan provider mock
  untuk pengembangan offline.
- **Ujian** — timer otoritatif di server, autosave, submit idempoten, umpan-balik AI,
  skor kemiripan.
- **Gamifikasi** — ruang (presence/leaderboard live via WebSocket), quest dengan pemilihan
  pemenang *fastest-valid* deterministik, tugas harian/mingguan, peringkat global/ruang/
  quest, notifikasi, dan badge dengan id on-chain. **XP & level (simulasi deterministik)**:
  XP dihitung dari aktivitas nyata (skor ujian terbaik, kemenangan quest, tugas, badge) —
  tidak pernah disimpan sehingga tak bisa drift — lalu dipetakan ke level dengan progres
  menuju level berikutnya di papan peringkat.
- **Panduan karier (simulasi)** — dashboard akademik (nilai, tren, radar minat, insight AI),
  tes kepribadian Big Five, rekomendasi jurusan AI dengan persetujuan guru BK
  (human-in-the-loop), roadmap milestone, ruang konsultasi BK, perpustakaan sumber, dan
  asisten AI berbasis aturan.
- **Reward Web3** — treasury, **ledger double-entry**, idempotent reward keys, outbox →
  blockchain worker → indexer, tautan explorer, dan penarikan (withdrawal).
- **Keamanan** — hashing Argon2id, sesi ter-hash dengan expiry/revocation, RBAC
  object-level, cookie CSRF-safe, CORS ketat, rate limiting, redaksi secret di log.
- **Sertifikat & komunitas (simulasi)** — sertifikat kredensial dengan ID unik dan
  halaman verifikasi publik; feed komunitas dengan posting, like, dan komentar.

---

## Tech stack

| Lapisan | Teknologi |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + asyncpg, Alembic, Redis, structlog |
| **AI** | Provider abstraksi (mock deterministik default; Google Gemini opsional) |
| **Web3** | web3.py, eth-account; kontrak Solidity ERC-1155 upgradeable (UUPS) via Hardhat + OpenZeppelin |
| **Worker** | Proses terpisah: `ai` (grading/generation), `blockchain`, `indexer` (pola `SELECT … FOR UPDATE SKIP LOCKED`) |
| **Frontend** | SvelteKit 2 + Svelte 5, TypeScript, Vite 5, Tailwind CSS 3, `adapter-node` |
| **Data** | PostgreSQL 16, Redis 7, MinIO (object storage) / local storage |
| **Tooling** | pytest, ruff, mypy, Vitest, Playwright, Hardhat, Docker Compose, Makefile |

---

## Arsitektur

```
Browser → SvelteKit → FastAPI ─┬─ PostgreSQL
                               ├─ Redis (queue, pub/sub, rate limit)
                               ├─ MinIO / local storage (materials)
                               └─ Workers: ai, blockchain, indexer
                                        └─ ERC-1155 OryphemCoin (Hardhat)
```

Backend berlapis: Router (`app/api/v1`) → Service (`app/services`) → Repository
(`app/repositories`) / Model (`app/models`) → Postgres. Lihat
[`docs/architecture.md`](docs/architecture.md) untuk gambaran lengkap.

---

## Instalasi

### Prasyarat

- **Docker** + Docker Compose v2
- **Node.js 20+** dan **npm**
- **Python 3.11+**
- (Opsional) **Foundry/Anvil** untuk chain lokal — sudah tersedia lewat image Docker

### Langkah cepat

```bash
git clone <repo-url> qloot && cd qloot

# 1. Konfigurasi environment
cp .env.example .env            # lalu isi/ubah secret (SESSION_SECRET, dsb.)

# 2. Install dependency (backend venv, frontend node_modules, contract deps)
make setup

# 3. Jalankan stack inti (postgres, redis, minio, backend, workers, frontend)
make up

# 4. Terapkan migrasi database
make db-migrate

# 5. Isi data demo + data bulk (>= 200 baris/tabel, 5 guru, 50 siswa)
make db-seed
```

Setelah selesai, buka:

| Layanan | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 |

> **Catatan.** `make db-migrate` dijalankan di dalam container (target `migrate`).
> Health check: `make health`. Lihat semua perintah dengan `make help`.

### Menjalankan tanpa Docker (mode dev)

```bash
# Backend (butuh Postgres + Redis yang bisa diakses)
make dev-backend                # uvicorn --reload di :8000

# Worker AI
make dev-worker

# Frontend
make dev-frontend               # vite dev di :3000
```

---

## Cara penggunaan

### Akun demo

Diperoleh dari `make db-seed`:

| Peran | Email | Password |
|---|---|---|
| Admin | `admin@qloot.example` | `AdminPass123!` |
| Guru | `teacher@qloot.example` | `TeacherPass123!` |
| Guru | `teacher2@qloot.example` | `TeacherPass123!` |
| Siswa | `student1@qloot.example` | `StudentPass123!` |
| Siswa | `student2@qloot.example` | `StudentPass123!` |

Bulk seed menambah hingga **5 guru** dan **50 siswa** (`teacher3…`, `student06…`, dst.)
yang tersebar di kelas `1A`, `1B`, `2A`, `2D`, `3A`, `3B`.

### Alur singkat

**Sebagai guru:**

1. Masuk, lalu buka **Panel Guru**.
2. **Pelajaran** — buat pelajaran, tentukan kelas & tipe kelas (IPA/IPS).
3. **Materi** — unggah PDF lalu *Generate questions* dengan AI; tinjau draf soal.
4. **Ujian** — susun ujian, publikasikan ke kelas.
5. **Quest** — atur hadiah per peringkat, publikasikan, lalu finalisasi pemenang.
6. **Jawaban** — lihat jawaban siswa, feedback AI, dan analitik.

**Sebagai siswa:**

1. Masuk dan buka **Dashboard** — isi nilai rapor langsung dari panel **Nilai akademik**.
2. **Pelajaran Saya** — ikuti pelajaran kelasmu dan selesaikan materi (materi terakhir
   yang selesai akan menerbitkan **sertifikat** otomatis).
3. **Ujian** — kerjakan ujian (timer server, autosave); lihat hasil & feedback AI.
4. **Ruang** — bergabung ke ruang live (leaderboard & event real-time via WebSocket).
5. **Quest / Tugas** — selesaikan untuk memperoleh OPC.
6. **Peringkat / Badge / Sertifikat** — pantau posisi dan pencapaian; sertifikat dapat
   diverifikasi publik lewat `/verify/<credential_id>`.
7. **Komunitas** — diskusi, like, dan komentar antar pelajar.
8. **Karier** — tes Big Five, rekomendasi jurusan & roadmap, konsultasi BK, asisten AI.
9. **Wallet** — lihat saldo, ledger, reward, kirim OPC internal, dan buat penarikan.

> **Lupa kata sandi?** Halaman `forgot-password` mengembalikan *reset token* di mode
> non-produksi (simulasi email), lalu gunakan halaman `reset-password` untuk menetapkan
> kata sandi baru.

### Akses API

Autentikasi berbasis cookie sesi (dari `/auth/login`) atau header
`Authorization: Bearer <token>`. Semua endpoint berada di prefix `/api/v1`.

```bash
# Login dan simpan cookie sesi
curl -s -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"student1@qloot.example","password":"StudentPass123!"}'

# Contoh: baca saldo wallet
curl -s -b cookies.txt http://localhost:8000/api/v1/wallet
```

---

## Seed data

`make db-seed` menjalankan seeder idempoten yang mengisi platform dengan data simulasi:

- **Akun** — 1 admin, **5 guru**, **50 siswa** yang tersebar di 6 kelas
  (`1A`, `1B`, `2A`, `2D`, `3A`, `3B`).
- **≥ 200 baris di setiap tabel** — pelajaran, lesson, materi, ujian, soal &
  opsi, attempt & jawaban, hasil penilaian, sertifikat, ruang & event,
  quest & pemenang, tugas & penyelesaian, reward & ledger, notifikasi,
  badge, papan peringkat, roadmap, konsultasi, resource, audit log, tabel
  blockchain, dsb. (Tabel yang memang dibatasi jumlahnya — `users`,
  `user_roles`, `wallet_accounts` — mengikuti spesifikasi akun, dan `roles`
  tetap berisi 3 peran keamanan.)
- **Materi PDF** — teks diekstrak dari **PDF edukasi asli dari internet**
  (catatan kuliah Stanford CS224n); bila jaringan tidak tersedia, seeder membuat PDF lokal
  sebagai fallback sehingga proses seeding selalu berhasil.
- **Aktivitas** — ujian yang sudah dinilai, quest yang difinalisasi beserta reward OPC,
  sertifikat, badge, notifikasi, dan data panduan karier.

Seeder aman dijalankan berulang kali (idempotent — id deterministik, guard unique
key). Untuk hanya menambah padding bulk:

```bash
make db-seed-bulk
```

---

## Pengujian

```bash
make test-unit         # backend pytest (butuh PostgreSQL)
make test-integration  # backend, penanda "integration"
make test-contracts    # Hardhat (kontrak ERC-1155)
make test-frontend     # Vitest
make test-e2e          # Playwright (butuh stack hidup)
make ci                # lint + typecheck + backend tests + contract tests
```

---

## Blockchain lokal

```bash
make blockchain-up                       # Anvil di :8545 (chain 31337)
make blockchain-build                    # kompilasi kontrak
make blockchain-test                     # uji kontrak
make blockchain-deploy NETWORK=localhost
make blockchain-show-all NETWORK=localhost
```

Deployment Sepolia dijaga (butuh konfirmasi eksplisit):

```bash
make blockchain-deploy NETWORK=sepolia CONFIRM_SEPOLIA=yes
make blockchain-verify  NETWORK=sepolia
make blockchain-publish NETWORK=sepolia
```

---

## Struktur repositori

```
apps/backend       FastAPI + SQLAlchemy async + Alembic + workers
apps/frontend      SvelteKit + TypeScript + Tailwind
blockchain         Hardhat + OpenZeppelin ERC-1155 (OryphemCoin)
infrastructure     proxy (Traefik/Nginx), monitoring (Prometheus/Grafana/Loki)
docs               architecture, api, blockchain, security, runbook
scripts            helper (check-env, e2e-scenario, blockchain-summary)
compose.yaml       development stack
compose.production.yaml  production overlay
Makefile           developer & ops entrypoint (jalankan `make help`)
```

---

## Keamanan

> **Jangan pernah commit secret.** Semua kredensial dibaca dari environment. Lihat
> [`docs/security.md`](docs/security.md). Jika private key, RPC URL, atau API key pernah
> ter-commit, anggap sudah bocor dan segera rotasi.

## Lisensi

MIT
