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

## Withdrawal settlement

A withdrawal **transfers pooled tokens to the user's personal wallet** — it is
not a burn. The custodial treasury/operator account holds the pooled OPT and
signs a `safeTransferFrom` (ERC-1155) to the approved `destination_address`:

1. The user requests a withdrawal; the ledger debit and fee are recorded and the
   amount is put on hold.
2. An admin approves it; only then is the `withdrawal` outbox item enqueued.
3. The worker transfers the amount from the operator account to the destination
   address and marks the request `submitted`.
4. The indexer waits for confirmations and marks it `completed`; a revert marks
   it `failed` and the ledger debit is refunded.

A withdrawal payload missing its destination is rejected retryably (never
burned). `verify_invariants()` (surfaced in `GET /blockchain/status/admin`)
checks that every asset contract is configured, the signer address is known,
the treasury is configured, and the signer holds `MINTER_ROLE` on OPT.

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

### Role handover & incident recovery

- Deploy with a deployer EOA, then grant `DEFAULT_ADMIN_ROLE`, `ADMIN_ROLE` and
  `PAUSER_ROLE` to the multisig and **renounce** them from the deployer.
- Keep `REWARDER_ROLE`/`MINTER_ROLE` only on the backend signer; rotate the
  signer key by granting the role to the new address before revoking the old.
- On a compromised signer: pause the affected asset (`PAUSER_ROLE`), revoke its
  roles from the multisig, then restart the worker with the new key.
- Production refuses to start with a placeholder secret or an incomplete live
  chain config (`BLOCKCHAIN_DRY_RUN=false` without OPT address, treasury, or
  signer key) so the system never silently runs in simulated mode.

## What is (and isn't) on-chain

**On-chain**: asset balances (OPT/QTC/ORT), mint/burn/reward events, ORX swaps
and AI-request burns, per-asset supply + caps, pause state, tx status, gas.

**Off-chain**: passwords, sessions, emails, names, exam answers, learning
documents, AI feedback, question drafts, badges/XP/rankings (gamification).

> All **asset and reward activity** is on-chain; **learning content and
> personal data** stays off-chain.
