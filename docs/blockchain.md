# QLoot Blockchain — aset digital (OPT · QTC · ORT + ORX)

See [`blockchain/README.md`](../blockchain/README.md) for the full reference.

## Contracts

QLoot deploys **four separate ERC-1155 UUPS contracts**, each with its own address:

| Code | Contract | File | Role | Supply |
|---|---|---|---|---|
| **OPT** | `OryphemToken` | `contracts/OryphemToken.sol` | Base currency | unlimited |
| **QTC** | `QlootChain` | `contracts/QlootChain.sol` | Premium chain asset (certificates, encrypted messages) | capped `1e15` |
| **ORT** | `OryphemIntelligence` | `contracts/OryphemIntelligence.sol` | AI credit (1 request = 1 ORT) | unlimited |
| **ORX** | `OryphemProxy` | `contracts/OryphemProxy.sol` | Router between OPT and QTC/ORT | — |

All three assets share `OryphemAssetBase` and use token id `0` within their own contract.

The **OryphemProxy (ORX)** router governs conversions: `1 ORT = 50 OPT`, `1 QTC = 1000 OPT`
(`swapOptFor`); `payAiRequest` burns 1 ORT per AI request. These rates are governable
storage: `ADMIN_ROLE` can call `setRates(optPerOrt, optPerQtc)` (emits `RatesUpdated`),
and `0` falls back to the immutable defaults. The backend quote (`ORX_ORT_RATE` /
`ORX_QTC_RATE`) must match the on-chain rates — a parity test enforces this.

### Extensions

`ERC1155Upgradeable` + `ERC1155SupplyUpgradeable` + `ERC1155PausableUpgradeable`
+ `ERC1155BurnableUpgradeable` + `AccessControlUpgradeable` + `UUPSUpgradeable`,
plus a custom transient-storage reentrancy guard.

### Roles

`DEFAULT_ADMIN_ROLE`, `ADMIN_ROLE`, `MINTER_ROLE`, `REWARDER_ROLE`,
`PAUSER_ROLE`, `URI_MANAGER_ROLE`, `ROUTER_ROLE`.

### Feature set

- Per-asset supply, `totalMinted`, `totalBurned`, optional circulating cap.
- Role-based mint/burn + `mintBatch`, idempotent `rewardUser` keyed by uint256.
- Pausable, per-tx + rolling daily mint caps, URI management.
- **ORX router**: `swapOptFor` (OPT → QTC/ORT at fixed rates), `payAiRequest`.
- **QTC anchoring**: `anchorDocument` (via ORX `anchorOnQtc`) stores an opaque
  document hash (e.g. a certificate's verification hash) under a unique key —
  hash only, no PII. This is QTC's functional sink: anchoring a certificate
  costs `1 QTC`.
- ORX totals: `totalOptSwappedIn`, `totalOrtMinted`, `totalQtcMinted`, `totalAiRequests`.

### Events

Standard ERC-1155 `TransferSingle`/`TransferBatch` plus:

```
// Each asset (OPT/QTC/ORT)
Minted(to, amount)
Burned(from, amount)
RewardPaid(to, amount, reason, idempotencyKey)
MaxSupplyUpdated(newMaxSupply)
LimitsUpdated(maxMintPerTx, dailyMintCap)
DocumentAnchored(anchorKey, documentHash, by)

// OryphemProxy (ORX)
Routed(account, qtcOrOrtId, optIn, assetOut)
AiRequestPaid(account, requests, totalRequests)
AssetsUpdated(opt, qtc, ort)
TreasuryUpdated(oldTreasury, newTreasury)
```

Only **opaque hashes** are emitted for off-chain references — never emails,
names, answers or scores.

## Upgrade path

Every contract is a UUPS proxy (upgrade-safe, appended storage only). Upgrade
all four, or one via `ASSET`:

```bash
make blockchain-deploy  NETWORK=localhost
make blockchain-upgrade NETWORK=localhost ASSET=ALL    # preserves all state
```

## Off-chain ↔ on-chain

- The backend computes reward idempotency keys off-chain and mirrors per-user
  balances in the double-entry ledger; on-chain asset balances are reconciled.
- The blockchain worker drains `transaction_outbox` (topics: `reward`,
  `airdrop`, `withdrawal`, `pause`, `unpause`, `swap`, `ai_request`,
  `certificate_anchor`); the indexer tracks confirmations and flips reward
  allocations to `confirmed`.
- In development (`BLOCKCHAIN_DRY_RUN=true`) an in-process fake chain returns
  deterministic pseudo-hashes so the whole pipeline runs offline.

## Roles & key management

Recommended production layout (identical role set on each asset):

| Role | Holder |
|---|---|
| `DEFAULT_ADMIN_ROLE` / `ADMIN_ROLE` | multisig (e.g. Safe) |
| `REWARDER_ROLE` | dedicated backend signer |
| `MINTER_ROLE` | backend signer / operations |
| `ROUTER_ROLE` | the OryphemProxy (ORX) contract |
| `PAUSER_ROLE` | multisig or security operator |
| `URI_MANAGER_ROLE` | multisig |

## What is (and isn't) on-chain

**On-chain**: asset balances (OPT/QTC/ORT), mint/burn/reward events, ORX swaps
and AI-request burns, per-asset supply + caps, pause state, tx status, gas.

**Off-chain**: passwords, sessions, emails, names, exam answers, learning
documents, AI feedback, question drafts, badges/XP/rankings (gamification).

> All **asset and reward activity** is on-chain; **learning content and
> personal data** stays off-chain.
