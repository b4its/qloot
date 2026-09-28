# Quality Gates

## 1. Test Pyramid

### Backend Unit/Service

- Validation, RBAC ownership, state transitions, idempotency, compensation.
- Reward key deterministic dan concurrent retry.
- Exam deadline/shuffle/grading/override/plagiarism.
- Task/quest verification dan timezone boundary.
- Wallet ledger invariant, reconciliation, withdrawal transitions.

### Backend Integration

- PostgreSQL transaction/locking dan Alembic upgrade/downgrade.
- Redis rate limit/pubsub/presence.
- Object storage presigned/local path dan AV quarantine.
- Worker + outbox + indexer + reorg/replacement.
- Local Anvil contract deployment dan Python client interaction.

### Frontend Component/Page

- Shared primitives: keyboard, ARIA, bind/callback, loading/error state.
- Route API state: success, empty, filtered-empty, partial, error, retry.
- Role guard dan object-level navigation.
- Search/filter/sort/pagination reset.
- Busy/idempotent action UI.

### E2E

1. Student onboarding → learning → exam → quest → reward → wallet.
2. Teacher campaign creation → publish → result review → override.
3. Admin user/reward/withdrawal/ledger/blockchain incident.
4. Career recommendation → counselor approval → roadmap.
5. Community report → moderation.
6. Realtime room reconnect/resync.
7. Certificate issue → anchor → public verify → revoke.

### Contract

- Role/cap/pause/reentrancy/idempotency.
- Transfer/mint/burn/swap/AI/anchor.
- Withdrawal settlement destination.
- UUPS authorization, storage layout, state preservation.
- Invariant/fuzz: supply, reward key, rate, allowance, batch limit.

## 2. Mandatory Commands

### Frontend Change

```bash
cd apps/frontend
npm run check
npm run lint
npm test -- --run
npm run build
```

Tambahan UI journey:

```bash
npx playwright test
```

### Backend Change

```bash
cd apps/backend
ruff check app tests
mypy app
pytest -q
```

### Contract/Chain Change

```bash
cd blockchain
npm test
npm run coverage
npx hardhat compile
```

### Repository Gate

```bash
make ci
```

Jika command tidak dapat dijalankan karena service eksternal, catat command, error, dependency,
dan test pengganti yang berhasil. Jangan menyebut item selesai tanpa bukti.

## 3. CI Gates yang Harus Ditambah

- Frontend route coverage, bukan hanya `src/lib/**`.
- Playwright Chromium, Firefox, WebKit, mobile viewport.
- Axe accessibility dan visual screenshot regression.
- Backend migration test dari release sebelumnya.
- Redis + Anvil integration job.
- Secret scanning, `pip-audit`, `npm audit`, container scan, SBOM.
- Slither dan UUPS storage-layout check.
- Image build/sign/provenance pada release.

## 4. Performance Budgets

- Landing LCP <= 2.5s pada simulated mobile; CLS <= 0.1.
- Initial JS per route diawasi; library chart/editor harus lazy-loaded.
- Search local terasa <100ms; server search debounce 200-300ms.
- API p95 read <500ms pada seed dataset; mutation <1s kecuali async job.
- Room event render tidak menyebabkan unbounded DOM/list growth.
- Animasi hanya transform/opacity dan tunduk reduced-motion.

## 5. Security Gates

- Tidak ada secret/raw private key/RPC credential dalam git atau log.
- Unsafe browser mutation wajib CSRF-valid.
- Auth/AI/upload/wallet endpoints rate-limited.
- File validation memakai magic bytes, size, sanitized key, quarantine/scan.
- CSV export mencegah formula injection.
- PII tidak masuk chain/event metadata.
- Admin critical action membutuhkan reason, confirm, audit request ID.
- Production menolak placeholder secret dan incomplete live-chain config.

## 6. Accessibility Gates

- Keyboard-only seluruh primary journey.
- Focus visible dan tidak terpotong clipped container.
- Dialog trap/restore focus.
- Live/error/status announcement.
- Progress semantic dan status tidak color-only.
- Text contrast AA light/dark.
- 200% zoom tanpa loss/overlap.
- Touch target dan mobile orientation.

## 7. Observability Gates

- Structured log membawa request/user/job/tx correlation tanpa secret.
- Metric: HTTP latency/error, auth rejection, AI job, grading failure, outbox age,
  chain failure, confirmation lag, reconciliation drift, negative/debt account.
- Alert: worker silence, failed outbox threshold, RPC down, ledger drift, DB/storage down.
- Runbook link tersedia pada alert.

## 8. Commit Review Template

```text
Scope:
Behavior changed:
Risk:
Tests added/updated:
Commands and results:
Migration/rollback:
Docs updated:
Accessibility/responsive evidence:
Simulation-first evidence:
```
