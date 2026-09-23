// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC1155Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC1155/ERC1155Upgradeable.sol";
import {ERC1155SupplyUpgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC1155/extensions/ERC1155SupplyUpgradeable.sol";
import {ERC1155PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC1155/extensions/ERC1155PausableUpgradeable.sol";
import {ERC1155BurnableUpgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC1155/extensions/ERC1155BurnableUpgradeable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {ReentrancyGuardTransientLocal} from "./utils/ReentrancyGuardTransientLocal.sol";

/**
 * @title OryphemAssetBase
 * @notice Shared, upgrade-safe ERC-1155 base for the QLoot digital assets
 *         (OPT, QTC, ORT). Each asset is deployed as its own ERC-1155 contract
 *         behind a UUPS proxy, so every asset has its own on-chain address.
 *
 * Common features:
 *  - ERC-1155 multi-token (the asset uses token id 0; extra ids are allowed).
 *  - Role-based mint/burn (MINTER_ROLE), rewarder payouts (REWARDER_ROLE).
 *  - Pausable transfers, burnable, per-tx + rolling daily mint caps.
 *  - Optional circulating supply cap (0 = unlimited).
 *  - Metadata `name()` / `symbol()` stored at init (upgrade-friendly).
 */
abstract contract OryphemAssetBase is
    Initializable,
    ERC1155Upgradeable,
    ERC1155SupplyUpgradeable,
    ERC1155PausableUpgradeable,
    ERC1155BurnableUpgradeable,
    AccessControlUpgradeable,
    ReentrancyGuardTransientLocal,
    UUPSUpgradeable
{
    // =====================================================================
    // Roles
    // =====================================================================
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant REWARDER_ROLE = keccak256("REWARDER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant URI_MANAGER_ROLE = keccak256("URI_MANAGER_ROLE");
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    /// @notice Role allowed to operate through the OryphemProxy (ORX) router.
    bytes32 public constant ROUTER_ROLE = keccak256("ROUTER_ROLE");

    /// @notice The asset's own primary token id (fixed at 0 for each asset).
    uint256 public constant ASSET_ID = 0;

    // =====================================================================
    // Storage
    // =====================================================================
    string private _assetName;
    string private _assetSymbol;

    /// @notice Maximum mint per transaction.
    uint256 public maxMintPerTx;
    /// @notice Rolling daily mint cap (per contract, all ids).
    uint256 public dailyMintCap;
    struct MintWindow {
        uint256 day;
        uint256 minted;
    }
    mapping(uint256 => MintWindow) public mintWindows;

    /// @notice Circulating-supply cap for ASSET_ID. 0 = unlimited.
    uint256 public maxSupply;
    /// @notice Total ever minted for ASSET_ID.
    uint256 public totalMinted;
    /// @notice Total ever burned for ASSET_ID.
    uint256 public totalBurned;
    /// @notice Tracked idempotency keys for `rewardUser`.
    mapping(uint256 => bool) public rewardKeyUsed;

    /// @notice On-chain anchors for opaque document hashes (e.g. certificate
    ///         hashes). Maps the caller-chosen anchor key to the stored hash.
    ///         Only the hash is stored — never any PII.
    mapping(bytes32 => bytes32) public documentAnchors;

    /// @dev Reserved storage for future upgrades (was [40]; one slot used).
    uint256[39] private __gap;

    // =====================================================================
    // Events
    // =====================================================================
    event Minted(address indexed to, uint256 amount);
    event Burned(address indexed from, uint256 amount);
    event RewardPaid(address indexed to, uint256 amount, bytes32 reason, uint256 idempotencyKey);
    event MaxSupplyUpdated(uint256 newMaxSupply);
    event LimitsUpdated(uint256 maxMintPerTx, uint256 dailyMintCap);
    event DocumentAnchored(bytes32 indexed anchorKey, bytes32 documentHash, address indexed by);

    // =====================================================================
    // Errors
    // =====================================================================
    error ZeroAdmin();
    error ZeroAccount();
    error ZeroAmount();
    error ExceedsMaxMintPerTx();
    error ExceedsDailyCap();
    error CapBelowMax();
    error MaxMintPerTxZero();
    error SupplyExceeded();
    error NotRewarder();
    error NotAuthorizedToBurn();
    error RewardKeyUsed();
    error LengthMismatch();
    error EmptyBatch();
    error BatchTooLarge();
    error AnchorKeyUsed();
    error ZeroAnchorKey();

    // =====================================================================
    // Init / metadata
    // =====================================================================
    function __OryphemAsset_init(
        string memory name_,
        string memory symbol_,
        string memory uri_,
        address admin,
        uint256 maxSupply_
    ) internal onlyInitializing {
        if (admin == address(0)) revert ZeroAdmin();
        __ERC1155_init(uri_);
        __ERC1155Supply_init();
        __ERC1155Pausable_init();
        __ERC1155Burnable_init();
        __AccessControl_init();

        _assetName = name_;
        _assetSymbol = symbol_;
        maxMintPerTx = 1_000_000;
        dailyMintCap = 10_000_000;
        maxSupply = maxSupply_;

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(URI_MANAGER_ROLE, admin);
        _grantRole(MINTER_ROLE, admin);
        _grantRole(REWARDER_ROLE, admin);
        _grantRole(ROUTER_ROLE, admin);
    }

    function name() external view returns (string memory) {
        return _assetName;
    }

    function symbol() external view returns (string memory) {
        return _assetSymbol;
    }

    function setURI(string calldata newUri) external onlyRole(URI_MANAGER_ROLE) {
        _setURI(newUri);
    }

    // =====================================================================
    // Limits / admin
    // =====================================================================
    function setLimits(uint256 maxMintPerTx_, uint256 dailyMintCap_)
        external
        onlyRole(ADMIN_ROLE)
    {
        if (maxMintPerTx_ == 0) revert MaxMintPerTxZero();
        if (dailyMintCap_ < maxMintPerTx_) revert CapBelowMax();
        maxMintPerTx = maxMintPerTx_;
        dailyMintCap = dailyMintCap_;
        emit LimitsUpdated(maxMintPerTx_, dailyMintCap_);
    }

    /// @notice Update the circulating-supply cap (0 = unlimited). Cannot go
    ///         below the current supply.
    function setMaxSupply(uint256 newMaxSupply) external onlyRole(ADMIN_ROLE) {
        if (newMaxSupply != 0 && newMaxSupply < totalSupply(ASSET_ID)) revert CapBelowMax();
        maxSupply = newMaxSupply;
        emit MaxSupplyUpdated(newMaxSupply);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // =====================================================================
    // Mint / burn
    // =====================================================================
    function mint(address to, uint256 amount) external onlyRole(MINTER_ROLE) {
        _checkAndAccumulateDaily(ASSET_ID, amount);
        _mint(to, ASSET_ID, amount, "");
        emit Minted(to, amount);
    }

    function burn(address from, uint256 amount) public virtual whenNotPaused {
        if (from != msg.sender && !isApprovedForAll(from, msg.sender)) revert NotAuthorizedToBurn();
        _burn(from, ASSET_ID, amount);
        emit Burned(from, amount);
    }

    /**
     * @notice Router-only burn used by the OryphemProxy (ORX) to settle swaps.
     * @dev Only the ROUTER_ROLE (the proxy) may call this; it burns from any
     *      account without a separate ERC-1155 approval because the router
     *      only ever settles a swap the account explicitly initiated.
     */
    function routerBurn(address from, uint256 amount) external onlyRole(ROUTER_ROLE) {
        if (from == address(0)) revert ZeroAccount();
        if (amount == 0) revert ZeroAmount();
        _burn(from, ASSET_ID, amount);
        emit Burned(from, amount);
    }

    /// @notice Router-only mint used by the OryphemProxy (ORX) to pay out swaps.
    function routerMint(address to, uint256 amount) external onlyRole(ROUTER_ROLE) {
        if (to == address(0)) revert ZeroAccount();
        _checkAndAccumulateDaily(ASSET_ID, amount);
        _mint(to, ASSET_ID, amount, "");
        emit Minted(to, amount);
    }

    /// @notice Mint to many recipients (gas-bounded).
    function mintBatch(address[] calldata recipients, uint256[] calldata amounts)
        external
        onlyRole(MINTER_ROLE)
    {
        uint256 len = recipients.length;
        if (len == 0) revert EmptyBatch();
        if (len > 200) revert BatchTooLarge();
        if (amounts.length != len) revert LengthMismatch();
        for (uint256 i = 0; i < len; i++) {
            _checkAndAccumulateDaily(ASSET_ID, amounts[i]);
            _mint(recipients[i], ASSET_ID, amounts[i], "");
            emit Minted(recipients[i], amounts[i]);
        }
    }

    // =====================================================================
    // Rewards
    // =====================================================================
    function rewardUser(address to, uint256 amount, bytes32 reason, uint256 idempotencyKey)
        external
        onlyRole(REWARDER_ROLE)
        whenNotPaused
    {
        if (rewardKeyUsed[idempotencyKey]) revert RewardKeyUsed();
        rewardKeyUsed[idempotencyKey] = true;
        _checkAndAccumulateDaily(ASSET_ID, amount);
        _mint(to, ASSET_ID, amount, "");
        emit RewardPaid(to, amount, reason, idempotencyKey);
    }

    // =====================================================================
    // Document anchoring (certificates / encrypted-message pointers)
    // =====================================================================
    /**
     * @notice Anchor an opaque document hash under a unique key.
     * @dev Writes only the hash on-chain (no PII). Idempotent per key: the same
     *      key cannot be anchored twice, so a certificate can be anchored at
     *      most once. Callable by ROUTER_ROLE (the operator/router).
     */
    function anchorDocument(bytes32 anchorKey, bytes32 documentHash)
        external
        onlyRole(ROUTER_ROLE)
        returns (bytes32)
    {
        if (anchorKey == bytes32(0)) revert ZeroAnchorKey();
        if (documentAnchors[anchorKey] != bytes32(0)) revert AnchorKeyUsed();
        documentAnchors[anchorKey] = documentHash;
        emit DocumentAnchored(anchorKey, documentHash, msg.sender);
        return documentHash;
    }

    /// @notice Whether `anchorKey` has been anchored, and its stored hash.
    function documentAnchorOf(bytes32 anchorKey) external view returns (bytes32) {
        return documentAnchors[anchorKey];
    }

    // =====================================================================
    // Internals
    // =====================================================================
    function _checkAndAccumulateDaily(uint256 tokenId, uint256 amount) internal {
        if (amount == 0) revert ZeroAmount();
        if (amount > maxMintPerTx) revert ExceedsMaxMintPerTx();

        uint256 today = block.timestamp / 1 days;
        MintWindow storage w = mintWindows[tokenId];
        if (w.day != today) {
            w.day = today;
            w.minted = 0;
        }
        if (w.minted + amount > dailyMintCap) revert ExceedsDailyCap();
        w.minted += amount;
    }

    function _update(address from, address to, uint256[] memory ids, uint256[] memory values)
        internal
        override(ERC1155Upgradeable, ERC1155SupplyUpgradeable, ERC1155PausableUpgradeable)
    {
        if (from == address(0)) {
            // Enforce the circulating supply cap on ASSET_ID mints.
            uint256 idAmount = 0;
            for (uint256 i = 0; i < ids.length; i++) {
                if (ids[i] == ASSET_ID) idAmount += values[i];
            }
            if (idAmount > 0) {
                if (maxSupply != 0 && totalSupply(ASSET_ID) + idAmount > maxSupply) {
                    revert SupplyExceeded();
                }
                totalMinted += idAmount;
            }
        } else if (to == address(0)) {
            uint256 idAmount = 0;
            for (uint256 i = 0; i < ids.length; i++) {
                if (ids[i] == ASSET_ID) idAmount += values[i];
            }
            totalBurned += idAmount;
        }
        super._update(from, to, ids, values);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC1155Upgradeable, AccessControlUpgradeable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    /// @dev Only admins may authorise an upgrade.
    function _authorizeUpgrade(address) internal override onlyRole(ADMIN_ROLE) {}
}
