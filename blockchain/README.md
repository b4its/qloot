# QLoot Blockchain — OryphemCoin (OPC)

## Contract

`OryphemCoin1155` (`blockchain/contracts/OryphemCoin1155.sol`) is a
**UUPS-upgradeable ERC-1155** that acts as the on-chain learning-state and
reward registry for QLoot.

### Token model

| Token id | Meaning |
|---|---|
| `0` | OPC balance (integer point unit, decimals 0) |
| `1_000_000 + badgeId` | Badge proof token (1 unit per awarded badge) |

### Extensions

- `ERC1155Upgradeable`, `ERC1155SupplyUpgradeable`, `ERC1155PausableUpgradeable`,
  `ERC1155BurnableUpgradeable`, `AccessControlUpgradeable`, `UUPSUpgradeable`
- Custom `ReentrancyGuardTransientLocal` (EIP-1153, zero storage slots → upgrade-safe)

### Roles

| Role | Purpose |
|---|---|
| `DEFAULT_ADMIN_ROLE` | Grant/revoke roles, upgrades |
| `ADMIN_ROLE` | Config: limits, treasury, courses, badges, levels |
| `MINTER_ROLE` | Mint/burn OPC, complete withdrawals |
| `REWARDER_ROLE` | Pay rewards, add XP, award badges, unlock achievements |
| `PAUSER_ROLE` | Pause/unpause |
| `URI_MANAGER_ROLE` | Set the metadata URI |

### Feature set

- **Balances**: per-user OPC mirror (`opcBalance`), `totalMinted`/`totalBurned`.
- **XP & level**: `addXp` (100 XP per level), `levelFromXp`, admin `setLevel`.
- **Courses**: `createCourse`/`setCourse`, `enroll`, `completeCourse` (pays OPC +
  XP + badge, idempotent per user+course), `courseCompletionCount`.
- **Badges**: `registerBadge` (uri + soulbound), `awardBadge` (idempotent, mints
  a proof token), soulbound badges blocked from transfer.
- **Achievements**: `unlockAchievement` with per-user counters.
- **Rewards**: idempotent `rewardUser` / `rewardUsers` (uint256 keys, batch ≤ 200).
- **Treasury**: `depositOPC` / `withdrawOPC` with per-account and global totals.
- **Safety**: pausable, reentrancy-guarded, per-tx and rolling daily mint caps.

### Events

`RewardPaid`, `XpAdded`, `LevelSet`, `CourseCreated`, `CourseUpdated`, `Enrolled`,
`CourseCompleted`, `BadgeRegistered`, `BadgeAwarded`, `AchievementUnlocked`,
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

```bash
make blockchain-build            # compile
make blockchain-test             # 47 tests

# Local (Anvil on :8545)
make blockchain-up NETWORK=localhost
make blockchain-deploy NETWORK=localhost
make blockchain-show-all NETWORK=localhost
make blockchain-create-badge NETWORK=localhost BADGE_ID=1 BADGE_URI="ipfs://b" SOULBOUND=true
make blockchain-create-course NETWORK=localhost COURSE_ID=1001 REWARD=500 BADGE_ID=1
make blockchain-add-xp NETWORK=localhost TO=0x.. AMOUNT=250
make blockchain-reward NETWORK=localhost TO=0x.. AMOUNT=100 REASON=quest KEY=1
make blockchain-course-state NETWORK=localhost ADDRESS=0x.. COURSE_ID=1001

# Sepolia (guarded with CONFIRM_SEPOLIA=yes)
make blockchain-deploy NETWORK=sepolia CONFIRM_SEPOLIA=yes
make blockchain-verify NETWORK=sepolia
make blockchain-publish NETWORK=sepolia
make blockchain-upgrade NETWORK=sepolia CONFIRM_SEPOLIA=yes
```

## Roles & key management

Never let one EOA hold everything. Recommended production layout:

| Role | Holder |
|---|---|
| `DEFAULT_ADMIN_ROLE` / `ADMIN_ROLE` | multisig (e.g. Safe) |
| `REWARDER_ROLE` | dedicated backend signer |
| `MINTER_ROLE` | backend signer / operations |
| `PAUSER_ROLE` | multisig or security operator |
| `URI_MANAGER_ROLE` | multisig |

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

Includes an upgrade path for the original `OryphemCoin1155` reward contract. If
you use the interface `IQLootAcademy`, the v2 contract implements every method.
