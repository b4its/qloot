// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import {ERC1155Supply} from "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Supply.sol";
import {ERC1155Pausable} from "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Pausable.sol";
import {ERC1155Burnable} from "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Burnable.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title OryphemCoin (OPC)
 * @notice ERC-1155 reward token for the QLoot gamified learning platform.
 *
 * Design notes:
 *  - Token ID 0 is the primary "reward" balance and is treated as an integer
 *    point unit (decimals are conceptually 0).
 *  - The treasury holds all tokens on-chain; individual user balances live in
 *    the QLoot off-chain double-entry ledger. On-chain events carry only
 *    opaque, salted hashes of user/quest references — never PII.
 *  - Rewards are idempotent: a rewardKey may only ever be finalized once.
 *  - A per-transaction mint cap and a per-epoch mint policy limit blast radius.
 *
 * ERC-1155 (EIP-1155) does not require name()/symbol(), so they are added here
 * and mirrored in the off-chain token metadata.
 */
contract OryphemCoin1155 is
    ERC1155,
    ERC1155Supply,
    ERC1155Pausable,
    ERC1155Burnable,
    AccessControl
{
    // ---------------------------------------------------------------------
    // Roles
    // ---------------------------------------------------------------------
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant REWARDER_ROLE = keccak256("REWARDER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant URI_MANAGER_ROLE = keccak256("URI_MANAGER_ROLE");

    /// @notice Primary reward token id.
    uint256 public constant OPC_TOKEN_ID = 0;

    // ---------------------------------------------------------------------
    // Limits / policy
    // ---------------------------------------------------------------------
    /// @notice Max amount that can be minted in a single mint call (per token id).
    uint256 public maxMintPerTx = 1_000_000;

    /// @notice Rolling daily mint cap (per token id), measured in whole tokens.
    uint256 public dailyMintCap = 10_000_000;

    struct MintWindow {
        uint256 day; // floor(block.timestamp / 1 days)
        uint256 minted; // amount minted within that day
    }

    /// tokenId => current window
    mapping(uint256 => MintWindow) public mintWindows;

    // ---------------------------------------------------------------------
    // Token metadata (ERC-1155 has no native name/symbol)
    // ---------------------------------------------------------------------
    string private _name;
    string private _symbol;

    /// @notice One-shot claim of a reward key.
    mapping(bytes32 => bool) public rewardFinalized;

    // ---------------------------------------------------------------------
    // Events
    // ---------------------------------------------------------------------
    event RewardGranted(
        bytes32 indexed rewardKey,
        bytes32 indexed userRef,
        uint256 indexed tokenId,
        uint256 amount,
        address treasury
    );

    event QuestRewardFinalized(
        bytes32 indexed questRef,
        bytes32 indexed rewardKey,
        bytes32 indexed userRef,
        uint8 rank,
        uint256 amount,
        address treasury
    );

    event CustodialAllocation(
        bytes32 indexed userRef,
        uint256 indexed tokenId,
        uint256 amount,
        address treasury
    );

    event CustodialTransfer(
        bytes32 indexed userRef,
        address indexed to,
        uint256 indexed tokenId,
        uint256 amount
    );

    event WithdrawalRequested(
        bytes32 indexed withdrawalRef,
        bytes32 indexed userRef,
        address indexed destination,
        uint256 tokenId,
        uint256 amount
    );

    event WithdrawalCompleted(
        bytes32 indexed withdrawalRef,
        address indexed destination,
        uint256 tokenId,
        uint256 amount,
        address operator
    );

    event MetadataPublished(string newUri, address publisher);

    event LimitsUpdated(uint256 maxMintPerTx, uint256 dailyMintCap);

    // ---------------------------------------------------------------------
    // Constructor
    // ---------------------------------------------------------------------
    constructor(
        string memory name_,
        string memory symbol_,
        string memory uri_,
        address admin
    ) ERC1155(uri_) {
        require(admin != address(0), "OPC: admin is zero");
        _name = name_;
        _symbol = symbol_;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        // Admin is also a temporary pauser/uri manager; production deployments
        // should move these to a multisig and revoke from the deployer EOA.
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(URI_MANAGER_ROLE, admin);
    }

    // ---------------------------------------------------------------------
    // Metadata
    // ---------------------------------------------------------------------
    function name() external view returns (string memory) {
        return _name;
    }

    function symbol() external view returns (string memory) {
        return _symbol;
    }

    function setURI(string calldata newUri) external onlyRole(URI_MANAGER_ROLE) {
        _setURI(newUri);
        emit MetadataPublished(newUri, msg.sender);
    }

    // ---------------------------------------------------------------------
    // Limits
    // ---------------------------------------------------------------------
    function setLimits(uint256 maxMintPerTx_, uint256 dailyMintCap_)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(maxMintPerTx_ > 0, "OPC: maxMintPerTx=0");
        require(dailyMintCap_ >= maxMintPerTx_, "OPC: cap < max");
        maxMintPerTx = maxMintPerTx_;
        dailyMintCap = dailyMintCap_;
        emit LimitsUpdated(maxMintPerTx_, dailyMintCap_);
    }

    // ---------------------------------------------------------------------
    // Minting
    // ---------------------------------------------------------------------
    function mint(address to, uint256 tokenId, uint256 amount, bytes calldata data)
        external
        onlyRole(MINTER_ROLE)
    {
        _checkAndAccumulateDaily(tokenId, amount);
        _mint(to, tokenId, amount, data);
    }

    function mintBatch(
        address to,
        uint256[] calldata tokenIds,
        uint256[] calldata amounts,
        bytes calldata data
    ) external onlyRole(MINTER_ROLE) {
        for (uint256 i = 0; i < tokenIds.length; i++) {
            _checkAndAccumulateDaily(tokenIds[i], amounts[i]);
        }
        _mintBatch(to, tokenIds, amounts, data);
    }

    // ---------------------------------------------------------------------
    // Reward recording (idempotent)
    // ---------------------------------------------------------------------
    /**
     * @notice Finalize a single reward for a user, minting into the treasury.
     * @dev Idempotent on rewardKey. Emits RewardGranted + QuestRewardFinalized.
     */
    function recordReward(
        bytes32 rewardKey,
        bytes32 questRef,
        bytes32 userRef,
        uint8 rank,
        address to,
        uint256 tokenId,
        uint256 amount
    ) external onlyRole(REWARDER_ROLE) {
        require(!rewardFinalized[rewardKey], "OPC: reward already finalized");
        require(to != address(0), "OPC: to is zero");
        require(amount > 0, "OPC: amount=0");

        rewardFinalized[rewardKey] = true;
        _checkAndAccumulateDaily(tokenId, amount);
        _mint(to, tokenId, amount, "");

        emit RewardGranted(rewardKey, userRef, tokenId, amount, to);
        emit QuestRewardFinalized(questRef, rewardKey, userRef, rank, amount, to);
    }

    /**
     * @notice Batch version of recordReward.
     */
    function recordRewards(
        bytes32[] calldata rewardKeys,
        bytes32[] calldata questRefs,
        bytes32[] calldata userRefs,
        uint8[] calldata ranks,
        address to,
        uint256 tokenId,
        uint256[] calldata amounts
    ) external onlyRole(REWARDER_ROLE) {
        uint256 len = rewardKeys.length;
        require(
            questRefs.length == len &&
                userRefs.length == len &&
                ranks.length == len &&
                amounts.length == len,
            "OPC: length mismatch"
        );
        require(to != address(0), "OPC: to is zero");

        for (uint256 i = 0; i < len; i++) {
            require(!rewardFinalized[rewardKeys[i]], "OPC: reward already finalized");
            require(amounts[i] > 0, "OPC: amount=0");

            rewardFinalized[rewardKeys[i]] = true;
            _checkAndAccumulateDaily(tokenId, amounts[i]);

            emit RewardGranted(rewardKeys[i], userRefs[i], tokenId, amounts[i], to);
            emit QuestRewardFinalized(
                questRefs[i],
                rewardKeys[i],
                userRefs[i],
                ranks[i],
                amounts[i],
                to
            );
        }
        _mint(to, tokenId, _sum(amounts), "");
    }

    /**
     * @notice Record a custodial allocation event without minting (book-keeping
     *         for off-chain ledger that already holds the balance).
     */
    function recordCustodialAllocation(
        bytes32 userRef,
        uint256 tokenId,
        uint256 amount,
        address treasury
    ) external onlyRole(REWARDER_ROLE) {
        require(treasury != address(0), "OPC: treasury is zero");
        require(amount > 0, "OPC: amount=0");
        emit CustodialAllocation(userRef, tokenId, amount, treasury);
    }

    // ---------------------------------------------------------------------
    // Withdrawal (treasury -> user wallet)
    // ---------------------------------------------------------------------
    function recordWithdrawalRequested(
        bytes32 withdrawalRef,
        bytes32 userRef,
        address destination,
        uint256 tokenId,
        uint256 amount
    ) external onlyRole(REWARDER_ROLE) {
        require(destination != address(0), "OPC: destination is zero");
        require(amount > 0, "OPC: amount=0");
        emit WithdrawalRequested(withdrawalRef, userRef, destination, tokenId, amount);
    }

    /**
     * @notice Complete a withdrawal by transferring treasury-held tokens to a
     *         user's destination address. Caller must be a minter (operator).
     */
    function completeWithdrawal(
        bytes32 withdrawalRef,
        address destination,
        uint256 tokenId,
        uint256 amount
    ) external onlyRole(MINTER_ROLE) {
        require(destination != address(0), "OPC: destination is zero");
        require(amount > 0, "OPC: amount=0");
        // Safe: _safeTransferFrom reverts on failure.
        _safeTransferFrom(msg.sender, destination, tokenId, amount, "");
        emit WithdrawalCompleted(withdrawalRef, destination, tokenId, amount, msg.sender);
    }

    // ---------------------------------------------------------------------
    // Pause
    // ---------------------------------------------------------------------
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // ---------------------------------------------------------------------
    // Internal helpers
    // ---------------------------------------------------------------------
    function _checkAndAccumulateDaily(uint256 tokenId, uint256 amount) internal {
        require(amount > 0, "OPC: amount=0");
        require(amount <= maxMintPerTx, "OPC: exceeds maxMintPerTx");

        uint256 today = block.timestamp / 1 days;
        MintWindow storage w = mintWindows[tokenId];
        if (w.day != today) {
            w.day = today;
            w.minted = 0;
        }
        require(w.minted + amount <= dailyMintCap, "OPC: exceeds daily cap");
        w.minted += amount;
    }

    function _sum(uint256[] calldata values) internal pure returns (uint256 total) {
        for (uint256 i = 0; i < values.length; i++) {
            total += values[i];
        }
    }

    // ---------------------------------------------------------------------
    // Required overrides
    // ---------------------------------------------------------------------
    function _update(address from, address to, uint256[] memory ids, uint256[] memory values)
        internal
        override(ERC1155, ERC1155Supply, ERC1155Pausable)
    {
        super._update(from, to, ids, values);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC1155, AccessControl)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
