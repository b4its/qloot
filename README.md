# QLoot

**QLoot** is a gamified, class-based e-learning platform with **AI-assisted exams**,
**competitive real-time rooms**, **quests & rankings**, and **blockchain rewards**
through the **OryphemToken (OPT)** ERC-1155 multi-token (OPT · QTC · ORT).

It is a ground-up reimplementation inspired by the domain of
[SayGenFix](https://github.com/mhaatha/saygenfix) (a Go/AI essay-exam app), rebuilt as
a **FastAPI + SvelteKit** monorepo with proper transactions, object-level RBAC,
background workers, and Web3 rewards.

> The whole platform runs as a **deterministic simulation** offline: the AI provider
> defaults to a mock, the chain client defaults to `dry_run`, and the career-guidance
> module is fully simulated — no external services or API keys are required to run,
> demo, or test the system.
>
> Optionally it can talk to a **real OpenAI-compatible AI gateway** (`AI_PROVIDER=openai`,
> e.g. a local DeepSeek endpoint) and to a **real EVM chain** (Sepolia), while staying
> simulation-first: rewards are always written to the double-entry ledger, and the
> blockchain worker only submits on-chain when `BLOCKCHAIN_DRY_RUN=false`.

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
- [Blockchain & OryphemToken (OPT)](#blockchain--oryphemtoken-opt)
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
  memperoleh **OryphemToken (OPT)**.
- **Admin** mengelola pengguna, hadiah, audit log, dan kontrol blockchain.

Setiap aktivitas bernilai (menyelesaikan quest, tugas, ujian sempurna, dsb.) menghasilkan
**reward OPC** yang dicatat pada **ledger double-entry**, diterbitkan sebagai event
*outbox* transaksional, lalu diproses oleh **blockchain worker** dan dikonfirmasi oleh
**indexer**.

---

## Fitur

- **Pembelajaran berbasis kelas** — pelajaran per kelas, materi, progres, dan PDF upload.
- **AI (mock / Gemini / OpenAI-compatible)** — pembuatan soal dari PDF, penilaian esai,
  ringkasan materi, dan tanya-jawab berbasis materi; struktur output tervalidasi, retry,
  dan provider mock deterministik untuk pengembangan offline. Asisten belajar/karier
  bernama **“Asisten Qlo”** (boleh dipanggil *Kulo*) dengan persona dari `ASSISTANT_NAME`.
- **Ujian** — timer otoritatif di server, autosave, submit idempoten, umpan-balik AI,
  skor kemiripan.
- **Gamifikasi** — ruang (presence/leaderboard live via WebSocket), quest dengan pemilihan
  pemenang *fastest-valid* deterministik, tugas harian/mingguan, peringkat global/ruang/
  quest, notifikasi, dan badge dengan id on-chain. **XP & level (simulasi deterministik)**:
  XP dihitung dari aktivitas nyata (skor ujian terbaik, kemenangan quest, tugas, badge) —
  tidak pernah disimpan sehingga tak bisa drift — lalu dipetakan ke level dengan progres
  menuju level berikutnya di halaman peringkat **dan profil**.
- **Panduan karier (simulasi)** — dashboard akademik (nilai, tren, radar minat, insight AI),
  tes kepribadian Big Five, rekomendasi jurusan AI dengan persetujuan guru BK
  (human-in-the-loop), roadmap milestone, ruang konsultasi BK, perpustakaan sumber, dan
  asisten AI berbasis aturan (fallback KB saat provider tidak tersedia).
- **Reward Web3** — treasury **wallet bersama** (custodial), **ledger double-entry** dengan
  saldo terfokus per-pengguna, idempotent reward keys, outbox → blockchain worker → indexer,
  tautan explorer, dan penarikan (withdrawal) ke wallet pribadi.
- **CRUD admin & pengajar** — guru membuat/mengubah/menghapus pelajaran, materi, ujian,
  soal, quest yang mereka miliki; admin mengelola peran pengguna serta mengaktifkan/
  menonaktifkan akun. Penghapusan dilindungi (menolak `409` bila sudah ada data anak,
  mis. ujian dengan attempt atau quest yang sudah difinalisasi).
- **Paginasi konsisten** — semua endpoint daftar dibatasi (`limit ≤ 200`) dan mendukung
  `offset`; komponen `Pagination.svelte` dipakai ulang di seluruh halaman berdata banyak.
- **Keamanan** — hashing Argon2id, sesi ter-hash dengan expiry/revocation, RBAC
  object-level, cookie CSRF-safe, CORS ketat, rate limiting, redaksi secret di log.
- **Sertifikat & komunitas (simulasi)** — sertifikat kredensial dengan ID unik dan
  halaman verifikasi publik; feed komunitas dengan posting, like, dan komentar.

---

## Tech stack

| Lapisan | Teknologi |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + asyncpg, Alembic, Redis, structlog |
| **AI** | Provider abstraksi: `mock` (deterministik, default), `gemini` (Google REST), atau `openai` (endpoint OpenAI-compatible apa pun, mis. gateway DeepSeek lokal) |
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
                                        └─ ERC-1155 OryphemToken (OPT · QTC · ORT)
                                           ├─ local: Anvil (chain 31337, dry-run)
                                           └─ Sepolia: proxy OPC (chain 11155111)
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
2. **Pelajaran** — buat pelajaran, tentukan kelas & tipe kelas (IPA/IPS); sunting/hapus
   materi (lesson) langsung dari daftar.
3. **Materi** — unggah PDF lalu *Buat soal* dengan AI; tinjau draf soal, hapus materi yang
   tidak dipakai.
4. **Ujian** — susun ujian, kelola soal (tambah/sunting/hapus), publikasikan, atau hapus
   ujian yang belum dikerjakan.
5. **Quest** — atur hadiah per peringkat, publikasikan, lalu finalisasi pemenang; hapus
   quest yang belum difinalisasi.
6. **Jawaban** — lihat jawaban siswa, feedback AI, dan analitik (berpaginasi).

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
9. **Wallet** — lihat saldo terfokusmu, ledger, reward, kirim OPC internal, dan buat penarikan ke
   wallet pribadi. **Ganti wallet** sendiri kapan saja (tempel alamat atau hubungkan MetaMask);
   setiap akun otomatis memakai wallet default platform (dibaca dari `.env`, tidak ditampilkan
   ke pengguna lain) sampai diubah.

**Sebagai admin:** kelola peran pengguna dan aktifkan/nonaktifkan akun (`/admin/users`),
tinjau hadiah (`/admin/rewards`), pantau blockchain (`/admin/blockchain`), dan audit log
(`/admin/audit`) — semuanya berpaginasi.

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

## Blockchain & OryphemToken (OPT)

**OryphemToken (OPT)** adalah kontrak **ERC-1155 multi-token** upgradeable (UUPS) +
OpenZeppelin yang menjadi registry aset digital QLoot. Satu kontrak memuat **3 aset** plus
token bukti badge:

| Token id | Simbol | Nama | Peran | Suplai |
|---|---|---|---|---|
| `0` | **OPT** | OryphemToken | Mata uang dasar (reward belajar) | **Tanpa batas** |
| `1` | **QTC** | QlootChain | Aset premium (sertifikat, enkripsi pesan) | **1e15** |
| `2` | **ORT** | OryphemIntelligence | Kredit layanan AI (1 request = 1 ORT) | Tanpa batas |
| `1_000_000 + badgeId` | — | Badge | Token bukti badge | 1 per badge |

**OryphemProxy (ORX)** adalah *router* on-chain yang mengatur konversi OPT ke aset lain:
**1 ORT = 50 OPT**, **1 QTC = 1000 OPT** (`swapOptFor` / `proxyRates`). Hanya **hash opaque**
yang di-emit on-chain — tidak pernah email, nama, jawaban, atau skor.

### Model wallet bersama (custodial) + saldo terfokus
Semua reward on-chain dicetak ke **satu wallet bersama** (treasury), sementara
**kepemilikan tiap pengguna dilacak per-akun** pada **ledger double-entry**
(`wallet_accounts.cached_balance`). Jadi saldo “milik dirinya sendiri” tetap jelas dan bisa
ditarik ke wallet pribadi, meski token fisik berada di satu wallet. Halaman **/wallet**
hanya menampilkan saldo terfokus milikmu dan **alamat wallet pribadimu sendiri** — alamat
wallet bersama/platform tidak pernah ditampilkan ke pengguna (hanya operator/admin, dan
alamatnya disimpan di `.env`, tidak di kode).

### Deployment Sepolia (live, terverifikasi)

Alamat kontrak, treasury, dan hash transaksi deploy **tidak** ditulis di repo ini. Semua nilai
runtime (contract/treasury) dibaca dari `.env` (`OPC_CONTRACT_ADDRESS`, `TREASURY_ADDRESS`),
sedangkan artefak deployment berada di `blockchain/deployments/*.json` dan
`blockchain/.openzeppelin/` yang **tidak di-track git** (lihat `.gitignore`). Setelah deploy,
salin alamatnya ke `.env` lokalmu; jangan pernah commit nilai-nilainya.

### Konfigurasi
`BLOCKCHAIN_DRY_RUN=true` (default) tetap **simulasi** — worker mengembalikan hash palsu
deterministik tanpa menyentuh jaringan. Untuk live, isi `.env` (lihat `.env.example`):

```bash
CHAIN_ID=11155111
BLOCKCHAIN_NETWORK=sepolia
SEPOLIA_RPC_URL=<rpc-url>                 # JANGAN commit
BLOCKCHAIN_PRIVATE_KEY=<deployer-key>     # JANGAN commit
ETHERSCAN_API_KEY=<key>                   # JANGAN commit
TREASURY_ADDRESS=<treasury-address>
DEFAULT_WALLET_ADDRESS=<default-personal-wallet>
OPC_CONTRACT_ADDRESS=<opc-proxy-address>
BLOCKCHAIN_DRY_RUN=true                    # ubah ke false untuk submit on-chain
```

### Perintah

Semua target menjalankan Hardhat di **host**. Untuk jaringan lokal, Makefile otomatis
memakai `LOCALHOST_RPC_URL=http://127.0.0.1:8545` (override dengan `RPC=http://host:port`).
Target yang butuh parameter akan **berhenti dengan pesan usage** jika variabel belum diisi
(tidak lagi berupa stack trace).

```bash
# --- Siklus lokal (Anvil, chain 31337) ---
make blockchain-up                       # jalankan Anvil di :8545 (docker)
make blockchain-down                     # hentikan + hapus Anvil & network
make blockchain-reset                    # hapus manifest lokal + state Anvil (mulai bersih)
make blockchain-redeploy                 # reset lalu deploy ulang ke lokal
make blockchain-build                    # kompilasi kontrak
make blockchain-test                     # 51 uji kontrak
make blockchain-deploy NETWORK=localhost # deploy proxy OryphemToken ke Anvil

# --- Inspeksi (lokal atau sepolia) ---
make blockchain-status NETWORK=localhost        # ringkas: name/symbol, supply, treasury
make blockchain-show-all NETWORK=localhost      # ringkas lengkap (supply, saldo, roles)
make blockchain-supply NETWORK=localhost TOKEN_ID=0
make blockchain-balance NETWORK=localhost ADDRESS=0xf39F… TOKEN_ID=0
make blockchain-events NETWORK=localhost        # dump event terbaru (LOOKBACK_BLOCKS=5000)

# --- Operasi token (contoh lokal; tambahkan CONFIRM_SEPOLIA=yes untuk sepolia) ---
make blockchain-mint NETWORK=localhost TO=0xf39F… AMOUNT=1000 TOKEN_ID=0   # 0=OPT 1=QTC 2=ORT
make blockchain-transfer NETWORK=localhost TO=0x7099… AMOUNT=250 TOKEN_ID=0  # [FROM=0x..]
make blockchain-swap NETWORK=localhost ASSET=2 AMOUNT=10        # ORX: beli 10 ORT (500 OPT)
make blockchain-ai-request NETWORK=localhost REQUESTS=1        # ORX: 1 request = 1 ORT
make blockchain-reward NETWORK=localhost TO=0x7099… AMOUNT=100 KEY=1 REASON=quest
make blockchain-add-xp NETWORK=localhost TO=0x7099… AMOUNT=250
make blockchain-create-badge NETWORK=localhost BADGE_ID=1 BADGE_URI=ipfs://.. SOULBOUND=true
make blockchain-award-badge NETWORK=localhost TO=0x7099… BADGE_ID=1
make blockchain-create-course NETWORK=localhost COURSE_ID=1001 REWARD=500 BADGE_ID=1 ACTIVE=true
make blockchain-set-course NETWORK=localhost COURSE_ID=1001 REWARD=750 BADGE_ID=1 ACTIVE=true
make blockchain-course-state NETWORK=localhost ADDRESS=0x7099… COURSE_ID=1001
make blockchain-pause NETWORK=localhost          # pause transfer
make blockchain-unpause NETWORK=localhost        # lanjutkan transfer
make blockchain-grant-role NETWORK=localhost ROLE=MINTER_ROLE ADDRESS=0x3C44…
make blockchain-revoke-role NETWORK=localhost ROLE=MINTER_ROLE ADDRESS=0x3C44…
make blockchain-upgrade NETWORK=localhost        # upgrade proxy ke implementation terbaru

# --- Sepolia (dijaga: butuh CONFIRM_SEPOLIA=yes) ---
make blockchain-deploy NETWORK=sepolia CONFIRM_SEPOLIA=yes
# deploy.js otomatis memverifikasi implementation + proxy (AUTO_VERIFY=false untuk melewatkan)
make blockchain-verify NETWORK=sepolia CONFIRM_SEPOLIA=yes   # verifikasi ulang bila perlu
make blockchain-publish NETWORK=sepolia
make blockchain-mint NETWORK=sepolia CONFIRM_SEPOLIA=yes TO=0x… AMOUNT=100
```

> **Reset vs down.** `blockchain-down` menghentikan Anvil dan menghapus network-nya
> (`down --remove-orphans`) sehingga `docker network` yang tertinggal tidak lagi
> menyebabkan error `network … not found` saat `blockchain-up` berikutnya.
> `blockchain-reset` menambahkan penghapusan state dan `deployments/<net>.json`
> (manifest lama menunjuk alamat kontrak yang tidak ada lagi di chain baru).

> Verifikasi memakai **Etherscan API v2** (satu API key universal). `verify.js`
> memverifikasi *implementation* lalu meng-*link* proxy UUPS ke implementation-nya.
> Karena `deploy.js` kini memanggil verifikasi otomatis, `blockchain-verify` hanya
> diperlukan bila verifikasi pertama gagal (mis. event `Upgraded` belum terindeks).

> **Keamanan produksi.** Deployer saat ini memegang `DEFAULT_ADMIN`/`MINTER`/`REWARDER`.
> Sebelum produksi, pindahkan role admin ke multisig dan berikan `MINTER`/`REWARDER` ke
> signer backend terdedikasi (lihat reminder di output `deploy.js`).


---

## AI gateway (opsional)

Default `AI_PROVIDER=mock` berjalan offline. Untuk memakai model nyata lewat endpoint
OpenAI-compatible (mis. gateway DeepSeek lokal pada `:20128`):

```bash
AI_PROVIDER=openai
AI_BASE_URL=http://host.docker.internal:20128/v1
AI_API_KEY=<key>
AI_GENERATION_MODEL=hk/deepseek-4.1-flash
AI_SCORING_MODEL=hk/deepseek-4.1-flash

make ai-gateway-allow   # izinkan container menjangkau gateway di host (butuh container privileged)
make ai-check           # verifikasi gateway terjangkau dari container backend
```

---

## Struktur repositori

```
apps/backend       FastAPI + SQLAlchemy async + Alembic + workers
apps/frontend      SvelteKit + TypeScript + Tailwind
blockchain         Hardhat + OpenZeppelin ERC-1155 (OryphemToken)
                   contracts/ · scripts/ · deployments/sepolia.*.json · .openzeppelin/
infrastructure     proxy (Traefik/Nginx), monitoring (Prometheus/Grafana/Loki)
docs               architecture, api, blockchain, security, runbook
scripts            helper (check-env, e2e-scenario, blockchain-summary, qloot-ai-gateway)
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
