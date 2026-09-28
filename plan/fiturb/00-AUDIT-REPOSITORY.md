# Audit Repository QLoot

## 1. Ringkasan Eksekutif

QLoot adalah monorepo pembelajaran bergamifikasi yang sudah matang secara fitur:

- FastAPI + SQLAlchemy async + PostgreSQL + Redis + MinIO/local storage.
- SvelteKit + Svelte 5 + TypeScript + Tailwind.
- AI mock/Gemini/OpenAI-compatible, RAG materi, generation dan grading job.
- Exam, room realtime, quest, task, ranking, XP, badge, notification, community, career.
- Ledger double-entry, outbox, blockchain worker/indexer/reconciler, tiga aset ERC-1155.
- 117+ test frontend, 87 modul test backend, Playwright, contract test, dan CI.

Masalah utama bukan kekurangan halaman. Masalah utama adalah **koherensi journey**, beberapa
risiko correctness/security produksi, fragmentasi primitive UI, dan design system yang masih
yellow-first meski target baru meminta blue-first.

## 2. Inventaris Folder

### Root

| Path | Peran | Catatan |
|---|---|---|
| `README.md` | Kontrak produk dan quick-start | Harus selalu sinkron dengan perilaku nyata |
| `Makefile` | Entry point dev/test/ops | Beberapa target security/lint masih perlu dibuat blocking |
| `compose.yaml` | Stack dev + profile chain/monitoring | Data network internal; MinIO dan chain opsional |
| `compose.production.yaml` | Overlay produksi | Single-host, belum HA |
| `.env.example` | Kontrak konfigurasi | Default AI harus konsisten dengan klaim simulation-first |

### `apps/backend`

- `app/api/v1/`: auth, course, material, AI, exam, room, quest, task, ranking,
  gamification, wallet, blockchain, career, community, certificate, social, teacher, admin.
- `app/services/`: aturan bisnis, reward engine, grading, realtime, storage, audit.
- `app/models/`: identity, learning, exam, quest/task, room, ranking, social, wallet,
  career, community, certificate, assistant.
- `app/workers/`: general/AI worker, blockchain worker, indexer, reconciler.
- `app/blockchain/`: dry-run/live client dan worker logic.
- `migrations/`: evolusi schema PostgreSQL.
- `tests/`: unit/integration lintas domain.

### `apps/frontend`

- `(landing)`: landing campaign.
- `(site)`: public + student app: dashboard, learning, exam, room, quest, task, ranking,
  badge, certificate, career, assistant, community, wallet, notification, profile.
- `(panel)/teacher`: content, material, exam, submission, quest, task, ranking, resource,
  consultation.
- `(panel)/admin`: user, reward, withdrawal, ledger, leaderboard, blockchain, audit,
  config, notification, moderation.
- `src/lib/components/`: primitive UI bersama. Primitive baru `FilterChips`, `SearchInput`,
  dan `MetricStrip` mengurangi markup berulang dan meningkatkan accessibility.
- `src/app.css` + `tailwind.config.ts`: design system cyberpunk yang saat ini yellow-first.

### `blockchain`

- `OryphemToken.sol` (OPT), `QlootChain.sol` (QTC), `OryphemIntelligence.sol` (ORT).
- `OryphemProxy.sol` (ORX) untuk swap/AI/anchoring.
- UUPS, role-based admin, cap, pause, idempotent reward key, test dan script deploy/upgrade.

### Infra dan Operasi

- `infrastructure/monitoring`: Prometheus, Grafana datasource, Loki.
- `infrastructure/proxy`: Nginx dan Traefik dynamic rules.
- `scripts/`: env check, E2E scenario, blockchain summary, AI gateway firewall helper.
- `.github/workflows/ci.yml`: backend, frontend, E2E, contract jobs.
- `docs/`: architecture, API, blockchain, security, runbook.

## 3. Kemampuan yang Sudah Utuh

### Identity dan Role

- Cookie session, rotation, revoke, logout-all, session list, password/email/profile/avatar.
- Student self-registration dan admin-created users.
- Role guard frontend dan object-level ownership backend.
- Audit log dan security middleware.

### Learning dan AI

- Course bertarget kelas, lesson reorder/publish, material PDF, extraction status.
- Student material view, progress, continue pointer, summary dan grounded Q&A.
- Question generation async/sync, review workflow, mock provider deterministik.
- Certificate issuance, render, verification, revoke, dan anchor flow.

### Exam

- Jendela buka/tutup, server-authoritative expiry, max attempt, shuffle, grace/penalty.
- MC deterministic grading, essay AI grading, autosave, submit idempoten.
- Question bank, reorder, regrade, manual override, analytics/CSV, plagiarism review.
- Proctoring telemetry sebagai konteks, bukan bukti otomatis.

### Gamification dan Realtime

- Quest fastest-valid deterministik dan reward rank.
- Task berperiode dan verifikasi aktivitas.
- Room membership/invite/presence/live events/WebSocket.
- XP/level derived, badge rarity/progress, leaderboard period, notification realtime.

### Wallet dan Chain

- Double-entry ledger, cached balance, reconciliation, transfer internal.
- OPT/QTC/ORT asset balance, swap, AI usage, withdrawal state machine.
- Transactional outbox, worker, indexer, stuck replacement, reorg handling.
- Dry-run deterministic dan live EVM path.

### Career dan Community

- Grade, personality, recommendation, counselor approval, roadmap, consultation thread.
- Career resources dan assistant history/stream.
- Community feed, like, comments/replies, follow, report, moderation.

## 4. Temuan dan Risiko Aktif

### P0: Correctness Web3

1. **Semantik withdrawal harus diverifikasi dan diperbaiki.** Jalur worker saat ini perlu
   dibuktikan mengirim aset ke `destination_address`, bukan hanya membakar saldo operator.
   Kriteria akhir: test lokal-chain memastikan saldo tujuan bertambah, ledger user terdebit
   sekali, retry idempoten, dan kegagalan memiliki kompensasi.
2. **Signer dan treasury invariant belum cukup terlihat.** Startup/admin health harus memeriksa
   chain ID, contract address, signer role, treasury identity/approval, dan pooled balance.
3. **Produksi harus fail-closed.** `BLOCKCHAIN_DRY_RUN=false` dengan alamat/key/RPC yang tidak
   lengkap tidak boleh diam-diam menghasilkan hash simulasi.

### P0: Security dan Privacy

1. Hook antivirus PDF masih no-op; integrasikan ClamAV/ICAP atau quarantine flow.
2. Tambahkan secret scanning, dependency/container scan, SBOM, Solidity static analysis,
   dan UUPS storage-layout gate ke CI.
3. Telemetry exam perlu notice, retensi, interpretasi threshold, dan appeal workflow.
4. Production startup harus menolak placeholder secret dan konfigurasi cookie/CORS yang lemah.

### P0: Product Coherence

1. Navigasi student berisi banyak destination tanpa pengelompokan mental yang kuat.
2. Quest, task, exam, room, badge, XP, certificate, dan OPT belum selalu tampil sebagai satu
   loop progres yang jelas.
3. Dashboard teacher belum sepenuhnya menjadi “next best action” untuk content, grading,
   intervensi siswa, dan campaign.
4. Admin economy belum menampilkan coverage/liability/budget dengan bahasa operasional yang
   mudah dipahami.

### P1: UX dan Accessibility

1. Shared primitives belum diadopsi semua list page; masih ada filter/search/KPI manual.
2. Empty/loading/error/retry states belum seragam pada sejumlah admin/teacher list.
3. Beberapa progress bar dan status dot belum punya semantic role/label lengkap.
4. Frontend route tests luas, tetapi coverage gate hanya menghitung `src/lib/**`.
5. E2E hanya desktop Chromium; belum mobile, Firefox/WebKit, axe, atau visual regression.

### P1: Visual Mismatch

Current design sudah cyberpunk, tetapi primary semantic masih acid yellow:

- `--accent` dan `primary` mengarah ke `#FCEE0A`.
- `btn-primary`, focus ring, scrollbar, active nav, glow, signature gradient dominan kuning.
- cyan masih secondary/data color.

Migrasi wajib semantic, bukan find-and-replace: kuning tetap dibutuhkan untuk OPT, warning,
legendary reward, dan hazard.

### P2: Institusi dan Skala

- Multi-school/tenant boundary, academic year lifecycle, guardian role, policy/consent minor.
- Curriculum/competency mapping, rubric versioning, accommodations, LMS/SIS export.
- Team/guild/class season, skill tree, PWA/offline/low-bandwidth.
- Managed deployment, HA, scheduled backups, alert rules, release signing/provenance.

## 5. Target North Star

### Student Loop

`Masuk kelas → lanjutkan lesson → checkpoint/ujian → quest/room → XP + OPT → badge →
certificate/QTC → roadmap berikutnya`

Setiap dashboard dan detail page harus menunjukkan:

- apa yang perlu dikerjakan sekarang;
- mengapa itu penting untuk pembelajaran;
- progres dan batas waktu;
- reward yang mungkin diperoleh;
- syarat validasi dan status settlement;
- langkah berikut setelah selesai.

### Teacher Loop

`Buat course → upload material → generate/review question → publish exam → hubungkan quest →
monitor submission → intervensi/regrade → lihat learning outcome dan reward budget`

### Admin Loop

`Kelola identitas → awasi trust/safety → jaga ledger dan treasury → review withdrawal →
monitor chain/workers → audit dan incident response`

## 6. Non-Goal

- Tidak membangun token spekulatif, marketplace, atau trading.
- Tidak membuat hasil AI menjadi keputusan akademik final tanpa human review.
- Tidak mengganti semua route/API hanya demi estetika.
- Tidak menambah animasi berat yang mengganggu exam, mobile, atau reduced-motion.
- Tidak menyentuh live network, private key, deployment, mint, atau upgrade tanpa persetujuan.
