# QLoot Security

## ⚠️ Secret handling (read this first)

Credentials of any kind — blockchain private keys, RPC URLs with embedded API keys,
Etherscan keys, AI keys, session secrets — must **never** be committed. If any of
these was ever exposed (in a repo, a chat, a log, a screenshot), treat it as
**compromised** and rotate it:

1. Do not reuse the old key for deployment.
2. Move any funds/assets off the affected address.
3. Create a new deployer wallet.
4. Revoke/delete the old Infura project & API key; create new ones.
5. Delete the old Etherscan key; create a new one.
6. Store new secrets in `.env` (gitignored), Docker secrets, CI secrets, or a
   secret manager (Vault/KMS).

`.env` is gitignored (`!.env.example` is kept). Private keys are only ever read
from the environment by the blockchain worker/toolbox — never passed on the
command line (which leaks to shell history and process lists).

## Backend checklist

- [x] Argon2id password hashing (`app/core/security.py`)
- [x] ≥256-bit random session tokens, stored **hashed** (HMAC-SHA256)
- [x] Session expiry + revocation + list/revoke-all
- [x] Login rate limiting / progressive account lockout
      (DB lockout after `login_max_attempts`; plus a Redis-backed per-IP window
      on `login`/`register`/`forgot-password`/`reset-password` and AI endpoints —
      see `RATE_LIMIT_*` in `app/core/config.py`; returns 429 + `Retry-After`)
- [x] Object-level authorization (owner or admin, never id alone)
- [x] Self-registration restricted to the `student` role (privileged roles are
      provisioned by an admin via `POST /admin/users`)
- [x] Strict CORS (no wildcard with credentials)
- [x] CSRF-safe cookies (`SameSite=Lax`, `HttpOnly`; `Secure` in prod)
- [x] File size limit + content-based PDF sniffing on upload
- [x] SQLAlchemy parameter binding (no string SQL)
- [x] Security headers middleware (CSP, HSTS in prod, nosniff, frame-deny)
- [x] Admin audit log
- [x] Secret redaction in structured logs
- [x] Idempotency keys for rewards and blockchain transactions
- [x] Request correlation id (`X-Request-ID`)
- [x] Containers run as non-root
- [x] DB backup/restore targets (`make db-backup` / `db-restore`)
- [ ] Antivirus scanning of uploaded documents (recommended add-on)
- [ ] Dependency scanning in CI (Dependabot/Renovate)

## Smart contract checklist

- [x] OpenZeppelin implementations
- [x] AccessControl with per-operation roles
- [x] Pausable transfers
- [x] Supply tracking
- [x] Idempotent reward keys
- [x] Max reward per tx + rolling daily mint cap
- [x] No PII on-chain
- [x] Unit + fuzz/invariant-style tests
- [ ] External audit
- [ ] Slither/Mythril in CI (recommended)
- [ ] Simulate on a testnet before mainnet
- [ ] Transfer roles to multisig; revoke deployer

## Reporting

If you discover a vulnerability, do **not** open a public issue with secrets or
exploit details. Rotate affected credentials first, then report privately.
