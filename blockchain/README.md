# QLoot Blockchain — digital assets (OPT · QTC · ORT + ORX)

## Contracts

QLoot deploys **four separate contracts** (each its own UUPS proxy → its own address):

| Code | Contract | File | Role | Supply |
|---|---|---|---|---|
| **OPT** | `OryphemToken` | `contracts/OryphemToken.sol` | Base currency | unlimited |
| **QTC** | `QlootChain` | `contracts/QlootChain.sol` | Premium chain asset (certificates, encrypted messages) | capped `1e15` |
| **ORT** | `OryphemIntelligence` | `contracts/OryphemIntelligence.sol` | AI credit (1 request = 1 ORT) | unlimited |
| **ORX** | `OryphemProxy` | `contracts/OryphemProxy.sol` | Router between OPT and QTC/ORT | — |

The three assets share `OryphemAssetBase` and use token id `0` in their own contract.

### OryphemProxy (ORX) — the router

`swapOptFor(assetId, amount)` converts OPT into ORT/QTC at fixed rates:
**1 ORT = 50 OPT**, **1 QTC = 1000 OPT** (`proxyRates()`/`ORT_RATE`/`QTC_RATE`).
`payAiRequest(requests)` burns ORT (1 request = 1 ORT). The ORX holds `ROUTER_ROLE`
on each asset so it can settle swaps (`routerBurn`/`routerMint`). QTC's cap is
enforced on every mint; OPT and ORT are uncapped.

### Extensions

- `ERC1155Upgradeable`, `ERC1155SupplyUpgradeable`, `ERC1155PausableUpgradeable`,
  `ERC1155BurnableUpgradeable`, `AccessControlUpgradeable`, `UUPSUpgradeable`
- Custom `ReentrancyGuardTransientLocal` (EIP-1153, zero storage slots → upgrade-safe)

### Roles

| Role | Purpose |
|---|---|
| `DEFAULT_ADMIN_ROLE` | Grant/revoke roles, upgrades |
| `ADMIN_ROLE` | Config: limits, supply cap, treasury, URI |
| `MINTER_ROLE` | Mint/burn the asset |
| `REWARDER_ROLE` | Pay idempotent rewards |
| `ROUTER_ROLE` | OryphemProxy (ORX) router burn/mint |
| `PAUSER_ROLE` | Pause/unpause |
| `URI_MANAGER_ROLE` | Set the metadata URI |

### Feature set

- **Assets**: OPT (unlimited), QTC (cap `1e15`), ORT (unlimited) — each a separate
  ERC-1155 UUPS contract; `totalMinted`/`totalBurned`, `maxSupply`, `setMaxSupply`.
- **Mint/burn**: `mint`, `mintBatch`, `routerMint`/`routerBurn`, `burn`.
- **Rewards**: idempotent `rewardUser` (uint256 keys).
- **OryphemProxy (ORX)**: `swapOptFor` (OPT→ORT/QTC at fixed rates), `payAiRequest`
  (1 request = 1 ORT), `proxyRates`, router totals.
- **Safety**: pausable, reentrancy-guarded, per-tx and rolling daily mint caps,
  custom errors (EIP-170 friendly bytecode).

### Events

`Minted`, `Burned`, `RewardPaid`, `MaxSupplyUpdated`, `LimitsUpdated` (assets);
`Routed`, `AiRequestPaid`, `AssetsUpdated`, `TreasuryUpdated` (ORX) — plus the
standard ERC-1155 `TransferSingle`/`TransferBatch`.

Only **opaque hashes** are used for off-chain references (user/quest refs) —
never emails, names or answers.

## Upgrade

The contracts are upgrade-safe (UUPS). Upgrade all four, or one via `ASSET`:

```bash
NETWORK=localhost make blockchain-upgrade ASSET=ALL
NETWORK=sepolia CONFIRM_SEPOLIA=yes make blockchain-upgrade ASSET=OPT
```

## Commands

All targets run Hardhat on the host. For local networks the Makefile forces
`LOCALHOST_RPC_URL=http://127.0.0.1:8545` (override with `RPC=http://host:port`),
and targets validate their required variables with a usage hint.

```bash
make blockchain-build            # compile
make blockchain-test             # 32 tests

# Local (Anvil on :8545, chain 31337)
make blockchain-up                        # start Anvil (docker)
make blockchain-down                      # stop + remove Anvil & its network
make blockchain-reset                     # wipe local manifests + Anvil state
make blockchain-redeploy                  # reset then deploy fresh locally
make blockchain-deploy NETWORK=localhost  # deploy OPT + QTC + ORT + ORX
make blockchain-status NETWORK=localhost  # all 4 contracts: addresses, supply, rates
make blockchain-show-all NETWORK=localhost
make blockchain-supply NETWORK=localhost ASSET=QTC          # ASSET=OPT|QTC|ORT
make blockchain-balance NETWORK=localhost ASSET=ORT ADDRESS=0x..
make blockchain-events NETWORK=localhost ASSET=ORX          # LOOKBACK_BLOCKS=5000
make blockchain-mint NETWORK=localhost ASSET=OPT TO=0x.. AMOUNT=100000
make blockchain-transfer NETWORK=localhost ASSET=OPT TO=0x.. AMOUNT=250
make blockchain-swap NETWORK=localhost ASSET=ORT AMOUNT=10  # ORX: OPT -> ORT/QTC
make blockchain-ai-request NETWORK=localhost REQUESTS=1     # ORX: pay with ORT
make blockchain-reward NETWORK=localhost ASSET=OPT TO=0x.. AMOUNT=100 REASON=quest KEY=1
make blockchain-pause NETWORK=localhost ASSET=OPT
make blockchain-unpause NETWORK=localhost ASSET=OPT
make blockchain-grant-role NETWORK=localhost ASSET=OPT ROLE=MINTER_ROLE ADDRESS=0x..

# Sepolia (guarded with CONFIRM_SEPOLIA=yes)
make blockchain-deploy NETWORK=sepolia CONFIRM_SEPOLIA=yes
# deploy.js auto-verifies all 4 implementations + proxies (AUTO_VERIFY=false to skip)
make blockchain-verify NETWORK=sepolia CONFIRM_SEPOLIA=yes
make blockchain-publish NETWORK=sepolia
make blockchain-upgrade NETWORK=sepolia CONFIRM_SEPOLIA=yes ASSET=ALL
```

> `ASSET` = `OPT` (default) | `QTC` | `ORT`, or `ORX`/`ALL` for upgrades.

> If `make blockchain-up` previously failed with `network … not found`, the stale
> container is now removed automatically; `blockchain-down` also deletes the
> network (`down --remove-orphans`) so the error does not recur.

## Roles & key management

Never let one EOA hold everything. Recommended production layout:

| Role | Holder |
|---|---|
| `DEFAULT_ADMIN_ROLE` / `ADMIN_ROLE` | multisig (e.g. Safe) |
| `REWARDER_ROLE` | dedicated backend signer |
| `MINTER_ROLE` | backend signer / operations |
| `PAUSER_ROLE` | multisig or security operator |
| `URI_MANAGER_ROLE` | multisig |
| `ROUTER_ROLE` | backend router signer |

After deployment, transfer roles to the multisig and revoke from the deployer EOA.

## What is (and isn't) on-chain

**On-chain**: token balances, XP/levels, course enrollment/completion counts,
badges and achievements, reward events, treasury deposits/withdrawals,
pause/role changes, tx status, gas.

**Off-chain**: passwords, sessions, emails, names, exam answers, learning
documents, AI feedback, question drafts.

> "Everything is on Etherscan" is scoped: all **asset, XP and reward activity**
> is on-chain, while **learning content and personal data** stays off-chain.

## Provenance

Includes an upgrade path for the original reward contract. If you use the
interface `IQLootAcademy`, `OryphemToken` implements every method.
