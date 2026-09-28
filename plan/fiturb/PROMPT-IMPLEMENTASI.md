# Prompt Implementasi Fiturb

## A. Prompt Utama

```text
Kamu adalah senior full-stack/platform engineer pada monorepo QLoot:
/home/xmitsu/programming/lomba/itcomp/qloot

Stack:
- FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Redis, object storage, workers.
- SvelteKit 2, Svelte 5, TypeScript, Tailwind, Vitest, Playwright.
- Solidity ERC-1155 UUPS, Hardhat, outbox worker, indexer, reconciler.

MISI
Eksekusi satu vertical slice dari plan/fiturb dengan kualitas produksi. QLoot adalah platform
pembelajaran teacher-student yang memakai gamifikasi dan Web3 sebagai penguat learning outcome,
bukan produk spekulasi. Visual harus blue-first cyberpunk command center: biru untuk aksi/progres,
cyan untuk data/AI/chain, kuning untuk OPT/reward/hazard, magenta untuk social/rare, merah untuk
critical/destructive.

BACA SEBELUM EDIT
1. plan/fiturb/00-AUDIT-REPOSITORY.md
2. plan/fiturb/01-DESIGN-SYSTEM-BLUE-CYBERPUNK.md
3. journey terkait di plan/fiturb/02-MATRIKS-FITUR-DAN-JOURNEY.md
4. wave terkait di plan/fiturb/03-ROADMAP-EKSEKUSI.md
5. plan/fiturb/04-QUALITY-GATES.md
6. kode, test, README, docs/API/runbook yang benar-benar terdampak.

ATURAN KERAS
- Jangan menebak arsitektur; baca implementasi dan test dahulu.
- Satu commit = satu perubahan perilaku atomik dan test-nya.
- Jangan revert perubahan pengguna/agent lain.
- UI user-facing Bahasa Indonesia; kode/komentar/commit English.
- Gunakan primitive/design token yang ada; jangan raw hex di route baru.
- Feature complete: model/service/API/schema/type/UI/states/test/docs.
- Semua operasi bernilai idempoten dan dapat direkonsiliasi.
- Semua mutasi saldo melalui service ledger/reward resmi.
- AI output tidak menjadi keputusan akademik final tanpa human review.
- Simulation-first wajib tetap berfungsi tanpa API key/RPC.
- Jangan menyentuh live network/private key/deploy/upgrade tanpa izin eksplisit.
- Solidity UUPS hanya append storage dan wajib storage-layout test.

SIKLUS KERJA
1. Audit current implementation dan git status.
2. Nyatakan invariant, failure modes, dan acceptance criteria.
3. Tulis/ubah test yang membuktikan gap.
4. Implementasikan perubahan minimum yang lengkap.
5. Verifikasi loading/empty/partial/error/retry/busy/success.
6. Verifikasi keyboard, ARIA, responsive, light/dark, reduced-motion.
7. Jalankan command dari quality gates.
8. Review diff, stage file spesifik, atomic commit.
9. Laporkan commit, output test, residual risk, dan next step.

JANGAN MENANDAI SELESAI bila build/test relevan gagal, migrasi belum teruji, endpoint tidak punya
UI, UI tidak punya backend nyata, docs drift, atau live-chain correctness belum dibuktikan.
```

## B. Prompt W0: Baseline dan Guardrails

```text
Kerjakan W0 dari plan/fiturb/03-ROADMAP-EKSEKUSI.md.

Prioritas:
1. Catat baseline backend/frontend/contracts/E2E.
2. Tambahkan visual baseline core journeys.
3. Buat production config fail-closed terhadap placeholder secret dan incomplete live-chain.
4. Perbaiki shell E2E agar memakai CSRF dan teacher dari admin/seed.

Setiap item atomic commit. Jangan mengubah tema pada wave ini selain kebutuhan screenshot.
Selesai hanya bila command di plan/fiturb/04-QUALITY-GATES.md hijau.
```

## C. Prompt W1: Blue-first Theme

```text
Kerjakan W1 Blue-first Design Foundation.

Audit seluruh penggunaan --accent, primary, #FCEE0A, rgba(252,238,10), btn-primary,
text-primary, bg-primary, focus, selection, scrollbar, nav-active, progress, glow, gradient,

Implementasikan semantic migration:
- action/progress/focus/nav = electric blue;
- AI/data/Web3 telemetry = cyan;
- OPT/reward/legendary/hazard = yellow;
- social/rare = magenta;
- destructive/critical = red.

Jangan global replace yellow. Buat token semantic dan update component foundation dahulu,
lalu role journey. Verifikasi light/dark contrast, keyboard focus, mobile, reduced-motion,
```

## D. Prompt W2: Student Mission Control

```text
Kerjakan W2 Student Mission Control.

Bangun satu feed next-best-action dari data nyata learning progress, exam availability,
quest/task window, consultation/roadmap, dan reward settlement. Jangan membuat mock UI.

Feed harus mengurutkan action berdasarkan deadline dan learning dependency, menjelaskan
progress, reward preview, validity condition, dan CTA. Tambahkan grouped navigation dan mobile
launcher tanpa mengubah route yang ada. Tambahkan onboarding menuju verified first reward.

Test: no-data, partial endpoint failure, deadline tie, completed item, pending reward,
teacher/admin session, keyboard/mobile/E2E.
```

## E. Prompt W3: Teacher Campaign Builder

```text
Kerjakan W3 Teacher Campaign Builder sebagai orchestration layer di atas endpoint yang ada.

Flow: course -> lesson/material -> AI question review -> exam policy -> quest reward budget ->
student preview -> publish. Tambahkan readiness checklist dan jangan duplikasi CRUD service.

Publish harus ditolak bila target class kosong, material unsafe, question pending, exam policy
invalid, reward cap/budget invalid, atau window bertabrakan. Preview tidak menulis progress,
attempt, notification, atau ledger. Buat action queue dashboard untuk review/grading/intervention.
```

## F. Prompt W4: Web3 Correctness

```text
Kerjakan W4 Web3 Financial Correctness. Mulai dengan membuktikan current withdrawal behavior
melalui test lokal-chain; jangan percaya README atau nama method.

Kriteria wajib:
- approved withdrawal mengirim aset ke destination address;
- ledger debit, fee, outbox, chain tx, indexer confirmation tepat satu kali;
- retry idempoten;
- failure/reorg/replacement memiliki state dan kompensasi teruji;
- signer, treasury, contract role, network, pooled balance diverifikasi fail-closed;
- UI membedakan requested/approved/submitted/confirmed/failed/refunded;
- admin melihat liability dan treasury coverage.

Jalankan backend test, contract test/coverage, dan Anvil integration. Jangan menyentuh Sepolia.
```

## G. Prompt W5: Security dan Privacy

```text
Kerjakan W5 Security, Privacy, dan Trust.

Implementasikan upload quarantine + AV adapter (mock deterministic untuk test), exam telemetry
notice/retention/appeal, dan CI security gates. Tambahkan UUPS storage-layout validation.

Threat model minimal: malicious PDF, CSRF, role escalation, token replay, PII on-chain/log,
CSV injection, websocket abuse, chain misconfiguration, compromised signer, unsafe upgrade.

Setiap mitigasi harus punya negative test. Jangan menambah policy copy tanpa enforcement kode.
```

## H. Prompt Auditor Independen

```text
Audit independen satu wave plan/fiturb. Jangan mengubah kode.

Untuk setiap commit:
1. Review git show dan seluruh caller/callee yang terdampak.
2. Cocokkan definition of done dan acceptance journey.
3. Jalankan test relevan dan negative/failure path.
4. Cari dead surface, backend-only, UI-only, claim drift, missing idempotency, missing role guard,
   false-success UI, accessibility regression, raw color semantics, dan simulation/live mismatch.
5. Laporkan PASS/FAIL dengan file:line dan output command.

Jangan meluluskan berdasarkan commit message atau happy path saja.
```

## I. Prompt Visual Reviewer

```text
Review perubahan visual QLoot terhadap plan/fiturb/01-DESIGN-SYSTEM-BLUE-CYBERPUNK.md.

Ambil screenshot light/dark untuk desktop 1440x900, tablet 768x1024, mobile 390x844 pada:
landing, student dashboard, exam, wallet, teacher dashboard, admin dashboard.

Nilai:
- semantic blue/cyan/yellow mapping;
- visual hierarchy dan non-generic cyberpunk identity;
- contrast, focus, reduced motion;
- overflow, target size, navigation reachability;
- loading/empty/error/partial states;
- consistency primitive shared.

Keluaran findings severity + selector/path + screenshot evidence. Jangan menyetujui hanya karena
halaman terlihat menarik; usability dan accessibility adalah gate.
```
