# QLoot Blockchain — OryphemToken (OPT · QTC · ORT)

See [`blockchain/README.md`](../blockchain/README.md) for the full reference.

## Contract

`OryphemToken` (`blockchain/contracts/OryphemToken.sol`) is a
**UUPS-upgradeable ERC-1155 multi-token** and the on-chain digital-asset registry for QLoot.

- Token id `0` = **OPT** (OryphemToken) balance — base currency, unlimited supply.
- Token id `1` = **QTC** (QlootChain) — premium asset, capped at `1e15`.
- Token id `2` = **ORT** (OryphemIntelligence) — AI credit (1 request = 1 ORT).
- Token id `1_000_000 + badgeId` = badge proof token.

The **OryphemProxy (ORX)** router governs conversions: `1 ORT = 50 OPT`, `1 QTC = 1000 OPT`.

### Extensions

### Extensions

`ERC1155Upgradeable` + `ERC1155SupplyUpgradeable` + `ERC1155PausableUpgradeable`
+ `ERC1155BurnableUpgradeable` + `AccessControlUpgradeable` + `UUPSUpgradeable`,
plus a custom transient-storage reentrancy guard.

### Roles

`DEFAULT_ADMIN_ROLE`, `ADMIN_ROLE`, `MINTER_ROLE`, `REWARDER_ROLE`,
`PAUSER_ROLE`, `URI_MANAGER_ROLE`.

### Feature set

- Per-user OPC balances, `totalMinted`, `totalBurned`.
- XP and level (100 XP per level) with `addXp` / `levelFromXp` / `setLevel`.
- Courses: create, enroll, complete (OPC + XP + badge, idempotent).
- Badges: registered metadata, soulbound or transferable, idempotent awards.
- Achievements: arbitrary unlockable achievements.
- Idempotent rewards keyed by uint256 keys (batch ≤ 200).
- Treasury accounting: deposits and withdrawals.
- Caps: per-transaction and rolling daily mint limits; pausable.

### Events

Standard ERC-1155 `TransferSingle`/`TransferBatch` plus:

```
RewardPaid(account, amount, reason, idempotencyKey)
XpAdded(account, amount, newTotalXp, newLevel)
LevelSet(account, newLevel)
CourseCreated(courseId, rewardAmount, badgeId)
CourseUpdated(courseId, rewardAmount, badgeId, active)
Enrolled(account, courseId)
CourseCompleted(account, courseId, reward, badgeId)
BadgeRegistered(badgeId, uri, soulbound)
BadgeAwarded(account, badgeId, tokenId)
AchievementUnlocked(account, achievementId)
Deposited(account, amount) / Withdrawn(account, amount)
TreasuryUpdated(oldTreasury, newTreasury)
V2Initialized(treasury, admin)
```

Only **opaque hashes** are emitted for off-chain references — never emails,
names, answers or scores.

## Upgrade path

The storage layout of the original reward contract is preserved; v2 state is
appended only. `initializeV2` is an idempotent reinitializer.

```bash
make blockchain-deploy  NETWORK=localhost
make blockchain-upgrade NETWORK=localhost    # preserves all state
```

## Off-chain ↔ on-chain

- The backend computes reward idempotency keys off-chain and mirrors per-user
  OPC balances; the on-chain `opcBalance` is reconciled against the ledger.
- The blockchain worker drains `transaction_outbox`; the indexer tracks
  confirmations and flips reward allocations to `confirmed`.
- In development (`BLOCKCHAIN_DRY_RUN=true`) an in-process fake chain returns
  deterministic pseudo-hashes so the whole pipeline runs offline.

## Roles & key management

Recommended production layout:

| Role | Holder |
|---|---|
| `DEFAULT_ADMIN_ROLE` / `ADMIN_ROLE` | multisig (e.g. Safe) |
| `REWARDER_ROLE` | dedicated backend signer |
| `MINTER_ROLE` | backend signer / operations |
| `PAUSER_ROLE` | multisig or security operator |
| `URI_MANAGER_ROLE` | multisig |

## What is (and isn't) on-chain

**On-chain**: token balances, XP/levels, course enrollment/completion, badges,
achievements, reward events, treasury deposits/withdrawals, tx status, gas.

**Off-chain**: passwords, sessions, emails, names, exam answers, learning
documents, AI feedback, question drafts.

> All **asset, XP and reward activity** is on-chain; **learning content and
> personal data** stays off-chain.
