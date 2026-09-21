# QLoot Blockchain — OryphemToken (OPT · QTC · ORT)

## Contract

`OryphemToken` (`blockchain/contracts/OryphemToken.sol`) is a
**UUPS-upgradeable ERC-1155 multi-token** that acts as the on-chain
digital-asset and reward registry for QLoot.

### Token model

| Token id | Symbol | Asset | Supply |
|---|---|---|---|
| `0` | **OPT** | OryphemToken (base currency) | unlimited |
| `1` | **QTC** | QlootChain (certificates, encrypted messages) | capped `1e15` |
| `2` | **ORT** | OryphemIntelligence (AI credit, 1 request = 1 ORT) | unlimited |
| `1_000_000 + badgeId` | — | Badge proof token (1 unit per awarded badge) | — |

### OryphemProxy (ORX) — the router

`swapOptFor(assetId, amount)` converts OPT into ORT/QTC at fixed rates:
**1 ORT = 50 OPT**, **1 QTC = 1000 OPT** (`proxyRates()`/`ORT_RATE`/`QTC_RATE`).
`payAiRequest(requests)` burns ORT (1 request = 1 ORT). The QTC cap is enforced on
every mint; OPT and ORT are uncapped (`maxSupplyOf(id)` returns `type(uint256).max`
for unlimited assets).

### Extensions

- `ERC1155Upgradeable`, `ERC1155SupplyUpgradeable`, `ERC1155PausableUpgradeable`,
  `ERC1155BurnableUpgradeable`, `AccessControlUpgradeable`, `UUPSUpgradeable`
- Custom `ReentrancyGuardTransientLocal` (EIP-1153, zero storage slots → upgrade-safe)

### Roles

| Role | Purpose |
|---|---|
| `DEFAULT_ADMIN_ROLE` | Grant/revoke roles, upgrades |
| `ADMIN_ROLE` | Config: limits, treasury, courses, badges, levels |
| `MINTER_ROLE` | Mint/burn OPT/QTC/ORT, complete withdrawals |
| `REWARDER_ROLE` | Pay rewards, add XP, award badges, unlock achievements |
| `ROUTER_ROLE` | OryphemProxy (ORX) router operations |
| `PAUSER_ROLE` | Pause/unpause |
| `URI_MANAGER_ROLE` | Set the metadata URI |

### Feature set

- **Assets**: OPT (id 0, unlimited), QTC (id 1, cap 1e15), ORT (id 2, unlimited);
  per-user OPT mirror (`opcBalance`), `totalMinted`/`totalBurned`, `maxSupplyOf(id)`.
- **XP & level**: `addXp` (100 XP per level), `levelFromXp`, admin `setLevel`.
- **Courses**: `createCourse`/`setCourse`, `enroll`, `completeCourse` (pays OPT +
  XP + badge, idempotent per user+course), `courseCompletionCount`.
- **Badges**: `registerBadge` (uri + soulbound), `awardBadge` (idempotent, mints
  a proof token), soulbound badges blocked from transfer.
- **Achievements**: `unlockAchievement` with per-user counters.
- **OryphemProxy (ORX)**: `swapOptFor` (OPT↔ORT/QTC at fixed rates), `payAiRequest`
  (1 request = 1 ORT), `proxyRates`/`maxSupplyOf`, router totals.
- **Rewards**: idempotent `rewardUser` / `rewardUsers` (uint256 keys, batch ≤ 200).
- **Treasury**: `depositOPC` / `withdrawOPC` with per-account and global totals.
- **Safety**: pausable, reentrancy-guarded, per-tx and rolling daily mint caps,
  custom errors (EIP-170 friendly bytecode).

### Events

`RewardPaid`, `XpAdded`, `LevelSet`, `CourseCreated`, `CourseUpdated`, `Enrolled`,
`CourseCompleted`, `BadgeRegistered`, `BadgeAwarded`, `AchievementUnlocked`,
`Swapped`, `AiRequestPaid`, `AssetMinted`,
`Deposited`, `Withdrawn`, `TreasuryUpdated`, `V2Initialized` — plus the standard
ERC-1155 `TransferSingle`/`TransferBatch`.

Only **opaque hashes** are used for off-chain references (user/quest refs) —
never emails, names or answers.

## Upgrade

The contract is upgrade-safe: the original v1 storage layout is preserved and
new state is appended only. `initializeV2(admin, treasury)` is a reinitializer
that runs once after an upgrade.

```bash
NETWORK=localhost make blockchain-upgrade
NETWORK=sepolia CONFIRM_SEPOLIA=yes make blockchain-upgrade
```

## Commands

All targets run Hardhat on the host. For local networks the Makefile forces
`LOCALHOST_RPC_URL=http://127.0.0.1:8545` (override with `RPC=http://host:port`),
and targets validate their required variables with a usage hint.

```bash
make blockchain-build            # compile
make blockchain-test             # 60 tests

# Local (Anvil on :8545, chain 31337)
make blockchain-up                        # start Anvil (docker)
make blockchain-down                      # stop + remove Anvil & its network
make blockchain-reset                     # wipe local manifests + Anvil state
make blockchain-redeploy                  # reset then deploy fresh locally
make blockchain-deploy NETWORK=localhost
make blockchain-status NETWORK=localhost
make blockchain-show-all NETWORK=localhost
make blockchain-supply NETWORK=localhost TOKEN_ID=0     # 0=OPT 1=QTC 2=ORT
make blockchain-balance NETWORK=localhost ADDRESS=0x.. TOKEN_ID=0
make blockchain-events NETWORK=localhost  # LOOKBACK_BLOCKS=5000
make blockchain-mint NETWORK=localhost TO=0x.. AMOUNT=1000 TOKEN_ID=0
make blockchain-transfer NETWORK=localhost TO=0x.. AMOUNT=250 TOKEN_ID=0
make blockchain-swap NETWORK=localhost ASSET=2 AMOUNT=10     # ORX: OPT -> ORT/QTC
make blockchain-ai-request NETWORK=localhost REQUESTS=1      # ORX: pay with ORT
make blockchain-create-badge NETWORK=localhost BADGE_ID=1 BADGE_URI="ipfs://b" SOULBOUND=true
make blockchain-award-badge NETWORK=localhost TO=0x.. BADGE_ID=1
make blockchain-create-course NETWORK=localhost COURSE_ID=1001 REWARD=500 BADGE_ID=1
make blockchain-set-course NETWORK=localhost COURSE_ID=1001 REWARD=750 BADGE_ID=1
make blockchain-add-xp NETWORK=localhost TO=0x.. AMOUNT=250
make blockchain-reward NETWORK=localhost TO=0x.. AMOUNT=100 REASON=quest KEY=1
make blockchain-course-state NETWORK=localhost ADDRESS=0x.. COURSE_ID=1001
make blockchain-pause NETWORK=localhost
make blockchain-unpause NETWORK=localhost

# Sepolia (guarded with CONFIRM_SEPOLIA=yes)
make blockchain-deploy NETWORK=sepolia CONFIRM_SEPOLIA=yes
# deploy.js auto-verifies implementation + proxy (AUTO_VERIFY=false to skip)
make blockchain-verify NETWORK=sepolia CONFIRM_SEPOLIA=yes
make blockchain-publish NETWORK=sepolia
make blockchain-upgrade NETWORK=sepolia CONFIRM_SEPOLIA=yes
```

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
