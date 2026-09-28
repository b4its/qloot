# Roadmap Eksekusi

## 1. Definition of Done

Sebuah item selesai hanya bila:

1. Jalur penuh model/service/API/schema/type/UI/state tersedia.
2. RBAC object-level, validation, idempotency, pagination, dan rate limit relevan lengkap.
3. Loading, empty, partial, error, retry, busy, success state lengkap.
4. Unit/integration/component/E2E/contract test relevan hijau.
5. Docs/README/API/runbook sinkron.
6. Simulation-first tetap berjalan.
7. Accessibility dan responsive acceptance terpenuhi.
8. Satu atomic commit yang dapat di-revert tanpa memutus item lain.

## 2. Urutan Wave

### W0: Baseline dan Guardrails

Tujuan: mengunci titik awal sebelum perubahan visual/produk besar.

- Jalankan seluruh test/check/lint/build backend/frontend/contracts.
- Tambahkan visual baseline lima halaman kunci.
- Dokumentasikan design token semantic dan forbidden raw colors.
- Perbaiki script E2E shell yang stale atau hapus dari jalur resmi.
- Buat production startup fail-closed untuk secret/chain config.

Target commit:

1. `docs(plan): add the blue cyberpunk Web3 learning master plan`
2. `test(ui): add visual baselines for core role journeys`
3. `fix(config): fail closed on invalid production secrets and chain settings`
4. `fix(e2e): align the shell scenario with CSRF and admin-created teachers`

### W1: Blue-first Design Foundation

Tujuan: migrasi semantic token tanpa menghilangkan makna OPT/hazard.

- Tambahkan neon blue/action/data/reward semantic variables.
- Ubah primary/focus/nav/button/progress ke blue-cyan.
- Pertahankan yellow untuk reward/hazard/legendary.
- Audit light/dark contrast, reduced motion, scrollbar, selection.
- Adopsi shared SearchInput/FilterChips/MetricStrip/Skeleton/EmptyState.

Target commit:

1. `feat(theme): introduce the blue-first semantic color system`
2. `refactor(ui): map primary interactions to blue and rewards to yellow`
3. `refactor(ui): standardize list controls and data states`
4. `test(a11y): cover contrast-critical and reduced-motion states`

### W2: Student Mission Control

- Unified next-action feed dari progress/exam/quest/task/career.
- Reward preview dan settlement state.
- Grouped navigation dan mobile launcher.
- Streak/level/goal visibility tanpa false urgency.
- Onboarding kelas → first lesson → first reward.

Target commit:

1. `feat(dashboard): add a unified student mission feed`
2. `feat(dashboard): explain progression and reward settlement`
3. `refactor(navigation): group the student app by learning journey`
4. `feat(onboarding): guide students to their first verified reward`

### W3: Teacher Campaign Builder

- Course → material → question → exam → quest stepper.
- Draft readiness checks dan student preview.
- Reward budget/cap preview.
- Publish validation dan class notification.
- Dashboard action queue.

Target commit:

1. `feat(teacher): add campaign readiness and next-step guidance`
2. `feat(teacher): preview student learning and assessment flows`
3. `feat(teacher): validate reward budgets before publishing quests`
4. `feat(teacher): add a grading and intervention action queue`

### W4: Web3 Financial Correctness

- Perbaiki/tegaskan withdrawal transfer semantics.
- Signer/treasury/role/balance health checks.
- Ledger-chain liability/coverage dashboard.
- User transaction lifecycle dan failure compensation.
- Multisig/role handover runbook.

Target commit:

1. `fix(withdrawals): settle approved requests to the destination wallet`
2. `feat(blockchain): verify signer treasury and contract role invariants`
3. `feat(admin): expose treasury coverage and settlement liabilities`
4. `feat(wallet): explain transaction lifecycle and recovery states`
5. `docs(blockchain): document multisig role handover and incident recovery`

### W5: Security, Privacy, dan Trust

- PDF quarantine/AV.
- Exam telemetry disclosure, retention, and appeal.
- Secret/SAST/dependency/container/Solidity scan.
- UUPS storage layout gate dan post-deploy role verifier.
- Data export/deletion and minor consent design.

Target commit:

1. `feat(storage): quarantine and scan uploaded learning materials`
2. `feat(exams): disclose telemetry and support review appeals`
3. `ci(security): add secret dependency container and Solidity scans`
4. `ci(contracts): validate UUPS storage layout changes`

### W6: Teacher Analytics dan Intervention

- Cohort mastery, item difficulty, misconception cluster.
- At-risk filter yang transparan dan non-punitive.
- Follow-up task/resource/consultation.
- Accommodation and extended-time policy.
- Gradebook/LMS export.

### W7: Social Gamification

- Team/class campaign dan seasonal leaderboard.
- Collaborative mission, not raw token farming.
- Anti-farming/rate/budget safeguards.
- Notification digest/preference.
- Community study-group bridge dengan moderation.

### W8: Institutional dan Production Scale

- School/tenant and academic-year lifecycle.
- Guardian/consent policy.
- HA deployment, scheduled backups/restore drill.
- Worker health, alert rules, log shipping.
- Signed image, SBOM, release provenance.

## 3. Status Implementasi

### Selesai

| Wave | Item | Commit |
|---|---|---|
| W0 | Master plan dan audit | `ab423e0` |
| W1 | Fondasi blue-first semantic color | `e54929f` |
| W1 | Standardisasi shared controls dan data states | `8d6fc9b`, `2b6088c`, `a2f45b6`, `396ed45`, `9128f24`, `d22c4ca`, `c8c32b4`, `e8a5966`, `d4c98f7`, `1dc2f9f`, `ea88f13`, `9600cfa` |
| W1 | Kontrak test tema dan a11y progress | `a34b93c`, `22a31e4` |
| W2 | Unified student mission feed | `d7ca40d` |
| W2 | Resilient learning continuation | `878216d` |
| W2 | Precise notification deep links | `e8c1eff` |
| W3 | Teacher action queue (grading, review, career, consultation) | `51184c9` |
| W4 | Withdrawal settles to the destination wallet (not burn) | `f9b1b9a` |
| W4 | Production fail-closed + signer/treasury/role invariants | `bb454a3` |
| W4 | Wallet settlement lifecycle explanation + runbook | `b0f4277` |
| W5 | Real malware policy on uploaded materials | `d7f276b` |
| W5 | Exam proctoring telemetry disclosure | `b8c3523` |
| W5 | E2E shell scenario aligned with CSRF + admin-created teacher | `4f30f8d` |
| W5 | CI secret/dependency/contract scan gates | `a60ee55` |
| W5 | Self-service data export + retention notice | `20ff9a6` |
| W4 | Admin custody invariant checks on blockchain hub | `42107d9` |
| W6 | Teacher cohort mastery + transparent at-risk analytics | `8170faa` |
| W7 | Per-user daily reward budget safeguard | `3d6b011` |
| W2 | Grouped student navigation by learning journey | `41328ef` |
| W2 | Student onboarding to first verified reward | `fa4a92c` |

### Berikutnya

Sisa item W2/W3 (campaign stepper, reward budget preview, student preview), sisa W5
(retention/appeal workflow backend, minor consent), sisa W7 (season/team, digest), dan W8
(institutional scale) belum dikerjakan dan tetap menjadi backlog terurut. Kerjakan sesuai
dependency graph di bagian berikut.

## 4. Dependency Graph

```text
W0 ──► W1 ──► W2 ──► W3
 │      │      │
 │      │      └────► W6
 │      └───────────► W7
 ├──────────────────► W4 ──► W8
 └──────────────────► W5 ──► W8
```

W4 dan W5 boleh berjalan paralel setelah baseline W0. W2/W3 baru dimulai setelah token visual
W1 stabil agar halaman tidak dimigrasikan dua kali.

## 5. Aturan Atomic Commit

- Satu commit = satu perilaku; test terkait berada di commit yang sama.
- Jangan mencampur token redesign, feature logic, dan formatting massal.
- Schema change memiliki satu Alembic revision dengan downgrade yang valid.
- Solidity storage hanya append; upgrade disertai storage-layout test.
- Stage file secara spesifik; jangan memasukkan generated timestamp/cache/artifact.
- Sebelum commit: `git status`, `git diff`, test relevan.
- Setelah wave: full suite + build + docs consistency.

## 6. Prioritas Backlog Ringkas

| Priority | Item | Outcome |
|---|---|---|
| P0 | Withdrawal destination settlement | Dana benar-benar sampai tujuan |
| P0 | Production fail-closed | Tidak ada simulasi/secrets lemah diam-diam |
| P0 | Signer/treasury invariants | Swap/burn/transfer tidak salah akun |
| P0 | AV/quarantine upload | Material berbahaya tidak tersebar |
| P0 | Blue semantic migration | Identitas visual sesuai permintaan |
| P1 | Student mission feed | Fitur gamifikasi menjadi satu loop |
| P1 | Teacher campaign builder | Authoring end-to-end lebih jelas |
| P1 | Economy admin dashboard | Liability/coverage actionable |
| P1 | Mobile/cross-browser/axe/visual tests | UX terbukti, bukan asumsi |
| P2 | Institutional lifecycle | Siap sekolah nyata/multi-tenant |
| P2 | Team seasons/skill tree | Diferensiasi setelah core aman |

## 7. Exit Criteria Release

- Tidak ada P0 terbuka.
- Backend/frontend/contracts unit suite hijau.
- E2E student/teacher/admin/Web3 flow hijau desktop dan mobile.
- Visual regression disetujui light/dark.
- Axe tidak memiliki serious/critical violation.
- Local-chain withdrawal membuktikan destination balance bertambah.
- Reconciliation menunjukkan zero unexplained drift.
- Runbook rollback/incident diuji pada staging.
