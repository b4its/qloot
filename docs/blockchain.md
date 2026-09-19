# QLoot Blockchain — OryphemCoin (OPC)

## Contract

`OryphemCoin1155` (`blockchain/contracts/OryphemCoin1155.sol`) is an ERC-1155
multi-token with:

- `ERC1155` + `ERC1155Supply` + `ERC1155Pausable` + `ERC1155Burnable`
- `AccessControl` with roles: `DEFAULT_ADMIN_ROLE`, `MINTER_ROLE`,
  `REWARDER_ROLE`, `PAUSER_ROLE`, `URI_MANAGER_ROLE`
- Custom `name()` / `symbol()` (ERC-1155 has neither)
- Primary reward token id `0`, integer point semantics (decimals 0)
- Idempotent `recordReward` / `recordRewards` keyed by `rewardKey`
- Per-transaction mint cap and rolling daily mint cap
- Custodial/withdrawal events

### Events

Standard ERC-1155 `TransferSingle`/`TransferBatch` plus:

```
RewardGranted(rewardKey, userRef, tokenId, amount, treasury)
QuestRewardFinalized(questRef, rewardKey, userRef, rank, amount, treasury)
CustodialAllocation(userRef, tokenId, amount, treasury)
CustodialTransfer(userRef, to, tokenId, amount)
WithdrawalRequested(withdrawalRef, userRef, destination, tokenId, amount)
WithdrawalCompleted(withdrawalRef, destination, tokenId, amount, operator)
MetadataPublished(newUri, publisher)
LimitsUpdated(maxMintPerTx, dailyMintCap)
```

Only **opaque hashes** (`userRef`, `questRef`, `rewardKey`) are emitted — never
emails, names, answers or scores.

## Commands

```bash
cd blockchain
npm install
npx hardhat compile
npx hardhat test                     # 23 tests

# Local (Anvil on :8545)
make blockchain-up
make blockchain-deploy NETWORK=localhost
make blockchain-show-all NETWORK=localhost
make blockchain-mint TO=0x.. AMOUNT=100
make blockchain-balance ADDRESS=0x..

# Sepolia (guarded)
make blockchain-deploy NETWORK=sepolia CONFIRM_SEPOLIA=yes
make blockchain-verify NETWORK=sepolia
make blockchain-publish NETWORK=sepolia
```

## Off-chain ↔ on-chain

- The backend computes `reward_key = sha256(quest_id|user_id|rank|reward_version)`
  and `user_ref` as a salted hash of the user id — matching what the contract
  stores, so idempotency holds on both sides.
- The blockchain worker drains `transaction_outbox` rows; the indexer tracks
  confirmations and flips reward allocations to `confirmed`.
- In development (`BLOCKCHAIN_DRY_RUN=true`) an in-process fake chain returns
  deterministic pseudo-hashes so the whole pipeline runs offline.

## Roles & key management

Never let one EOA hold everything. Recommended production layout:

| Role | Holder |
|---|---|
| `DEFAULT_ADMIN_ROLE` | multisig (e.g. Safe) |
| `REWARDER_ROLE` | dedicated backend signer |
| `MINTER_ROLE` | backend signer / operations |
| `PAUSER_ROLE` | multisig or security operator |
| `URI_MANAGER_ROLE` | multisig |

After deployment, transfer roles to the multisig and revoke from the deployer EOA.

## What is (and isn't) on-chain

**On-chain**: token supply, transfers, rewards, quest finalization events,
withdrawals, pause/role changes, tx status, gas.

**Off-chain**: passwords, sessions, emails, names, exam answers, learning
documents, AI feedback, question drafts.

> "Everything is on Etherscan" is scoped: all **asset/reward activity** is on-chain,
> while **learning and personal data** stays off-chain.
