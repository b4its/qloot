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
 * @title OryphemToken (OPT) — QLoot Academy
 * @notice ERC-1155 multi-token registry for the QLoot digital-asset economy.
 *         One contract holds three fungible assets plus badge proof tokens:
 *           - id 0 = OPT (OryphemToken)     — base currency, unlimited supply.
 *           - id 1 = QTC (QlootChain)       — premium chain asset, capped 1e15.
 *           - id 2 = ORT (OryphemIntelligence) — AI-service credit (1 req = 1 ORT).
 *           - id >= BADGE_TOKEN_OFFSET       — badge proof tokens (1 unit each).
 *
 *         The **OryphemProxy (ORX)** is the on-chain router that governs
 *         conversion between OPT and the other assets via a rate registry:
 *           1 ORT = 50 OPT      (ORT_RATE)
 *           1 QTC = 1000 OPT    (QTC_RATE)
 *
 * Feature groups:
 *  - ERC-1155 multi-token with per-user balances (OPT/QTC/ORT + badges).
 *  - XP + level per user (level can be granted directly or derived from XP).
 *  - Courses: create/activate, enroll, completeCourse (pays OPT + XP + badge).
 *  - Badges: metadata registry + soulbound or transferable, per-user awards.
 *  - Achievements: arbitrary achievements unlock via `unlockAchievement`.
 *  - OryphemProxy router: configurable rates + OPT<->asset swaps, AI requests.
 *  - Treasury accounting: deposits/withdrawals and a mints-minus-burns counter.
 *  - Idempotent rewards (`rewardUser` / `rewardUsers`) keyed on a uint256 key.
 *  - Burn/mint/pause when active, gas-safe batch cap, reentrancy guard.
 *  - Per-asset supply caps (OPT unlimited, QTC 1e15; ORT unlimited).
 *
 * Upgrade safety:
 *  - The original contract's storage layout is preserved verbatim via the
 *    legacy block below. New state is appended only.
 *  - `initializeV2` initialises the v2 modules and is idempotent.
 *
 * Security:
 *  - Every state-changing entry point is role-gated or self-scoped.
 *  - `nonReentrantLocal` guards all external-value-moving functions.
 *  - Only registered badges are recognized; soulbound badges cannot transfer.
 */
contract OryphemToken is
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
    /// @notice Role allowed to move assets through the OryphemProxy router.
    bytes32 public constant ROUTER_ROLE = keccak256("ROUTER_ROLE");

    /// @notice OPT — base currency (OryphemToken), unlimited supply (token id 0).
    uint256 public constant OPT_TOKEN_ID = 0;
    /// @notice QTC — QlootChain premium asset, capped supply.
    uint256 public constant QTC_TOKEN_ID = 1;
    /// @notice ORT — OryphemIntelligence AI-service credit.
    uint256 public constant ORT_TOKEN_ID = 2;
    /// @notice Token id space for badges starts at this offset.
    uint256 public constant BADGE_TOKEN_OFFSET = 1_000_000;
    /// @notice Maximum recipients in a single rewardUsers call (gas safety).
    uint256 public constant MAX_BATCH = 200;
    /// @notice XP required per level (Level 1 needs LEVEL_XP_STEP XP, etc.).
    uint256 public constant LEVEL_XP_STEP = 100;

    /// @notice OPT has no supply cap (base currency). Kept as a constant for
    ///         a uniform per-asset query surface; `type(uint256).max` = unlimited.
    uint256 public constant MAX_OPT_SUPPLY = type(uint256).max;
    /// @notice QTC (id 1) circulating-supply cap: 1e15 (QlootChain is limited).
    uint256 public constant MAX_QTC_SUPPLY = 1_000_000_000_000_000;
    /// @notice ORT (id 2) has no hard cap; AI credits are minted on demand.
    uint256 public constant MAX_ORT_SUPPLY = type(uint256).max;

    /// @notice OryphemProxy router rates, expressed in OPT per 1 unit of asset.
    ///         1 ORT = 50 OPT.
    uint256 public constant ORT_RATE = 50;
    ///         1 QTC = 1000 OPT.
    uint256 public constant QTC_RATE = 1000;

    // =====================================================================
    // Legacy storage (original v1 layout — DO NOT REORDER)
    // =====================================================================
    uint256 public maxMintPerTx;
    uint256 public dailyMintCap;
    struct MintWindow {
        uint256 day;
        uint256 minted;
    }
    mapping(uint256 => MintWindow) public mintWindows;
    string private _legacyName;
    string private _legacySymbol;
    mapping(bytes32 => bool) public rewardFinalized;

    // =====================================================================
    // New storage (v2 — appended only)
    // =====================================================================
    /// @notice Treasury address that custodies the assets on-chain.
    address public treasury;
    /// @notice Monotonic per-user base-currency (OPT, id 0) balances mirrored on-chain.
    mapping(address => uint256) public opcBalance;
    /// @notice Per-user experience points.
    mapping(address => uint256) public xp;
    /// @notice Per-user level.
    mapping(address => uint32) public level;
    /// @notice Total XP ever distributed.
    uint256 public totalXpDistributed;
    /// @notice Total base-currency (OPT, id 0) minted all time.
    uint256 public totalMinted;
    /// @notice Total base-currency (OPT, id 0) burned all time.
    uint256 public totalBurned;

    /// @notice Idempotency keys for rewards (uint256 keyed).
    mapping(uint256 => bool) public rewardKeyUsed;

    /// @notice Course id => configuration.
    struct Course {
        uint256 rewardAmount; // OPT paid on completion
        uint8 badgeId; // badge granted on completion
        bool active; // available for enrollment
    }
    mapping(uint256 => Course) public courses;
    /// @notice Whether a course id has ever been created.
    mapping(uint256 => bool) public courseExists;
    /// @notice account => courseId => enrolled
    mapping(address => mapping(uint256 => bool)) public enrolled;
    /// @notice account => courseId => completed
    mapping(address => mapping(uint256 => bool)) public completed;
    /// @notice courseId => number of completions.
    mapping(uint256 => uint256) public courseCompletionCount;
    /// @notice Total courses created.
    uint256 public totalCourses;

    /// @notice Badge id => metadata.
    struct Badge {
        string uri;
        bool soulbound;
        bool exists;
    }
    mapping(uint8 => Badge) public badges;
    /// @notice account => badgeId => awarded.
    mapping(address => mapping(uint8 => bool)) public hasBadge;
    /// @notice account => number of badges awarded.
    mapping(address => uint256) public userBadgeCount;
    /// @notice badgeId => minted supply.
    mapping(uint8 => uint256) public badgeSupply;

    /// @notice achievement id => unlocked (per user).
    mapping(address => mapping(bytes32 => bool)) public achievementUnlocked;
    /// @notice account => number of achievements unlocked.
    mapping(address => uint256) public achievementCount;

    /// @notice account => cumulative deposits.
    mapping(address => uint256) public depositOf;
    uint256 public totalDeposits;
    uint256 public totalWithdrawals;

    /// @notice Whether initializeV2 has been run.
    bool public v2Initialized;

    // =====================================================================
    // OryphemProxy (ORX) router storage
    // =====================================================================
    /// @notice account => cumulative AI requests paid with ORT.
    mapping(address => uint256) public aiRequestsOf;
    /// @notice Total AI requests served across all accounts.
    uint256 public totalAiRequests;
    /// @notice Cumulative OPT routed into the proxy (swapped for another asset).
    uint256 public totalOptSwappedIn;
    /// @notice Cumulative ORT minted through the proxy (OPT -> ORT).
    uint256 public totalOrtMinted;
    /// @notice Cumulative QTC minted through the proxy (OPT -> QTC).
    uint256 public totalQtcMinted;

    /// @dev Reserved storage to allow future upgrades without shifting layout.
    uint256[35] private __gap;

    // =====================================================================
    // Events
    // =====================================================================
    event XpAdded(address indexed account, uint256 amount, uint256 newTotalXp, uint32 newLevel);
    event LevelSet(address indexed account, uint32 newLevel);
    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    event CourseCreated(uint256 indexed courseId, uint256 rewardAmount, uint8 badgeId);
    event CourseUpdated(uint256 indexed courseId, uint256 rewardAmount, uint8 badgeId, bool active);
    event Enrolled(address indexed account, uint256 indexed courseId);
    event CourseCompleted(
        address indexed account,
        uint256 indexed courseId,
        uint256 reward,
        uint8 badgeId
    );
    event BadgeRegistered(uint8 indexed badgeId, string uri, bool soulbound);
    event BadgeAwarded(address indexed account, uint8 indexed badgeId, uint256 tokenId);
    event AchievementUnlocked(address indexed account, bytes32 indexed achievementId);
    event RewardPaid(address indexed account, uint256 amount, bytes32 reason, uint256 idempotencyKey);
    event Deposited(address indexed account, uint256 amount);
    event Withdrawn(address indexed account, uint256 amount);
    event V2Initialized(address treasury, address admin);
    /// @notice Emitted when OPT is routed through the OryphemProxy into another asset.
    event Swapped(
        address indexed account,
        address indexed router,
        uint256 optIn,
        uint256 assetId,
        uint256 assetOut
    );
    /// @notice Emitted when an AI request is paid with ORT (1 request = 1 ORT).
    event AiRequestPaid(address indexed account, uint256 ortBurned, uint256 totalRequests);
    /// @notice Emitted when the router pays out an asset (course/reward/airdrop).
    event AssetMinted(address indexed account, uint256 tokenId, uint256 amount);
    // =====================================================================
    // Custom errors (compact — cheaper than revert strings for EIP-170)
    // =====================================================================
    error ZeroAccount();
    error AchievementIdZero();
    error AchievementAlreadyUnlocked();
    error ZeroAdmin();
    error AlreadyCompleted();
    error AlreadyEnrolled();
    error ZeroAmount();
    error BadgeExists();
    error BadgeIdZero();
    error BadgeSoulbound();
    error BadgeNotRegistered();
    error BatchTooLarge();
    error CapBelowMax();
    error CourseExists();
    error CourseInactive();
    error EmptyBatch();
    error ExceedsDailyCap();
    error ExceedsDeposit();
    error ExceedsMaxMintPerTx();
    error InsufficientBalance();
    error InsufficientORT();
    error LengthMismatch();
    error LevelCannotDecrease();
    error MaxMintPerTxZero();
    error NoSuchCourse();
    error NotAuthorizedToBurn();
    error NotEnrolled();
    error NotRewarder();
    error QtcSupplyExceeded();
    error RateMismatch();
    error ZeroRequests();
    error RewardKeyUsed();
    error ZeroRecipient();
    error ZeroTreasury();
    error UnsupportedAsset();

    // =====================================================================
    // Modifiers
    // =====================================================================
    modifier whenNotPausedNow() {
        _requireNotPaused();
        _;
    }

    // =====================================================================
    // Initializers
    // =====================================================================
    /**
     * @notice Initialise a brand-new deployment. For a freshly deployed proxy
     *         this sets everything up directly. On an existing v1 deployment the
     *         `initializeV2` function is used instead.
     */
    function initialize(
        string memory name_,
        string memory symbol_,
        string memory uri_,
        address admin,
        address treasury_
    ) external initializer {
        if (!(admin != address(0))) revert ZeroAdmin();
        __ERC1155_init(uri_);
        __ERC1155Supply_init();
        __ERC1155Pausable_init();
        __ERC1155Burnable_init();
        __AccessControl_init();

        _legacyName = name_;
        _legacySymbol = symbol_;
        maxMintPerTx = 1_000_000;
        dailyMintCap = 10_000_000;

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(URI_MANAGER_ROLE, admin);
        _grantRole(MINTER_ROLE, admin);
        _grantRole(REWARDER_ROLE, admin);
        _grantRole(ROUTER_ROLE, admin);

        treasury = treasury_ == address(0) ? admin : treasury_;
        v2Initialized = true;
        emit V2Initialized(treasury, admin);
    }

    /**
     * @notice Initialise the v2 modules on an upgraded (previously v1) proxy.
     * @dev Idempotent; safe to call once after `upgradeToAndCall`.
     */
    function initializeV2(address admin, address treasury_) external reinitializer(2) {
        if (!(admin != address(0))) revert ZeroAdmin();

        if (!hasRole(ADMIN_ROLE, admin)) _grantRole(ADMIN_ROLE, admin);
        if (!hasRole(DEFAULT_ADMIN_ROLE, admin)) _grantRole(DEFAULT_ADMIN_ROLE, admin);
        if (!hasRole(ROUTER_ROLE, admin)) _grantRole(ROUTER_ROLE, admin);

        if (maxMintPerTx == 0) maxMintPerTx = 1_000_000;
        if (dailyMintCap == 0) dailyMintCap = 10_000_000;
        if (treasury_ != address(0)) treasury = treasury_;
        v2Initialized = true;
        emit V2Initialized(treasury, admin);
    }

    // =====================================================================
    // Metadata
    // =====================================================================
    function name() external view returns (string memory) {
        return _legacyName;
    }

    function symbol() external view returns (string memory) {
        return _legacySymbol;
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
        if (!(maxMintPerTx_ > 0)) revert MaxMintPerTxZero();
        if (!(dailyMintCap_ >= maxMintPerTx_)) revert CapBelowMax();
        maxMintPerTx = maxMintPerTx_;
        dailyMintCap = dailyMintCap_;
    }

    function setTreasury(address newTreasury) external onlyRole(ADMIN_ROLE) {
        if (!(newTreasury != address(0))) revert ZeroTreasury();
        emit TreasuryUpdated(treasury, newTreasury);
        treasury = newTreasury;
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // =====================================================================
    // XP / level
    // =====================================================================
    /// @notice XP required to reach a given level (level 1 => 0 XP).
    function xpForLevel(uint32 lvl) public pure returns (uint256) {
        if (lvl <= 1) return 0;
        return uint256(lvl - 1) * LEVEL_XP_STEP;
    }

    /// @notice Derive the level implied by a given XP amount.
    function levelFromXp(uint256 xpAmount) public pure returns (uint32) {
        return uint32(xpAmount / LEVEL_XP_STEP) + 1;
    }

    /**
     * @notice Add XP to an account and recompute its level.
     * @dev XP only ever increases. Level follows `levelFromXp`.
     *      Callable by rewarders, or internally by course completion.
     */
    function addXp(address account, uint256 amount) public {
        if (!(hasRole(REWARDER_ROLE, msg.sender) || msg.sender == address(this))) revert NotRewarder();
        _addXp(account, amount);
    }

    /// @dev Internal XP grant used by role-gated callers and completeCourse.
    function _addXp(address account, uint256 amount) internal {
        if (!(account != address(0))) revert ZeroAccount();
        if (!(amount > 0)) revert ZeroAmount();

        xp[account] += amount;
        totalXpDistributed += amount;
        uint32 newLevel = levelFromXp(xp[account]);
        if (newLevel > level[account]) {
            level[account] = newLevel;
        }
        emit XpAdded(account, amount, xp[account], level[account]);
    }

    /// @notice Grant a level directly (admin escape hatch / correction).
    function setLevel(address account, uint32 newLevel) external onlyRole(ADMIN_ROLE) {
        if (!(account != address(0))) revert ZeroAccount();
        if (!(newLevel >= level[account])) revert LevelCannotDecrease();
        level[account] = newLevel;
        emit LevelSet(account, newLevel);
    }

    // =====================================================================
    // Courses
    // =====================================================================
    function createCourse(
        uint256 courseId,
        uint256 rewardAmount,
        uint8 badgeId,
        bool active
    ) public onlyRole(ADMIN_ROLE) {
        if (!(!courseExists[courseId])) revert CourseExists();
        if (!(badgeId == 0 || badges[badgeId].exists)) revert BadgeNotRegistered();
        courses[courseId] = Course({rewardAmount: rewardAmount, badgeId: badgeId, active: active});
        courseExists[courseId] = true;
        totalCourses += 1;
        emit CourseCreated(courseId, rewardAmount, badgeId);
    }

    function setCourse(
        uint256 courseId,
        uint256 rewardAmount,
        uint8 badgeId,
        bool active
    ) public onlyRole(ADMIN_ROLE) {
        if (!(courseExists[courseId])) revert NoSuchCourse();
        if (!(badgeId == 0 || badges[badgeId].exists)) revert BadgeNotRegistered();
        courses[courseId] = Course({rewardAmount: rewardAmount, badgeId: badgeId, active: active});
        emit CourseUpdated(courseId, rewardAmount, badgeId, active);
    }

    /// @notice Enroll the caller in an active course.
    function enroll(uint256 courseId) external whenNotPausedNow {
        if (!(courseExists[courseId])) revert NoSuchCourse();
        if (!(courses[courseId].active)) revert CourseInactive();
        if (!(!enrolled[msg.sender][courseId])) revert AlreadyEnrolled();
        enrolled[msg.sender][courseId] = true;
        emit Enrolled(msg.sender, courseId);
    }

    /**
     * @notice Complete a course: pays OPT, grants XP and awards the course badge.
     * @dev Idempotent per (user, course). Requires prior enrollment.
     */
    function completeCourse(uint256 courseId)
        external
        whenNotPausedNow
        nonReentrantLocal
        returns (uint256 reward)
    {
        if (!(courseExists[courseId])) revert NoSuchCourse();
        if (!(enrolled[msg.sender][courseId])) revert NotEnrolled();
        if (!(!completed[msg.sender][courseId])) revert AlreadyCompleted();

        Course memory c = courses[courseId];
        completed[msg.sender][courseId] = true;
        courseCompletionCount[courseId] += 1;

        // Pay the course reward if any.
        if (c.rewardAmount > 0) {
            _payReward(msg.sender, c.rewardAmount, keccak256("course"), courseId);
        }
        // Grant XP equal to the reward (or 10 when there is no reward).
        _addXp(msg.sender, c.rewardAmount > 0 ? c.rewardAmount : 10);

        if (c.badgeId != 0) {
            _awardBadge(msg.sender, c.badgeId);
        }
        emit CourseCompleted(msg.sender, courseId, c.rewardAmount, c.badgeId);
        return c.rewardAmount;
    }

    // =====================================================================
    // Badges / achievements
    // =====================================================================
    function registerBadge(uint8 badgeId, string calldata uri, bool soulbound)
        public
        onlyRole(ADMIN_ROLE)
    {
        if (!(badgeId != 0)) revert BadgeIdZero();
        if (!(!badges[badgeId].exists)) revert BadgeExists();
        badges[badgeId] = Badge({uri: uri, soulbound: soulbound, exists: true});
        emit BadgeRegistered(badgeId, uri, soulbound);
    }

    /// @notice Award a registered badge to `to`. Idempotent per (to, badgeId).
    function awardBadge(address to, uint8 badgeId, string calldata uri)
        public
        onlyRole(REWARDER_ROLE)
        returns (uint256 tokenId)
    {
        if (!(badges[badgeId].exists)) revert BadgeNotRegistered();
        // Allow the caller to supply metadata if the badge has no URI yet.
        if (bytes(badges[badgeId].uri).length == 0 && bytes(uri).length > 0) {
            badges[badgeId].uri = uri;
        }
        return _awardBadge(to, badgeId);
    }

    /**
     * @notice Unlock an arbitrary achievement for the caller or a target.
     * @dev Awarders can unlock for any account; a user may also self-unlock a
     *      purely cosmetic achievement.
     */
    function unlockAchievement(address account, bytes32 achievementId)
        external
        onlyRole(REWARDER_ROLE)
    {
        _unlockAchievement(account, achievementId);
    }

    // =====================================================================
    // Rewards
    // =====================================================================
    /**
     * @notice Pay an idempotent OPT reward to `to`.
     * @dev Reverts if `idempotencyKey` was used before.
     */
    function rewardUser(
        address to,
        uint256 amount,
        bytes32 reason,
        uint256 idempotencyKey
    ) public onlyRole(REWARDER_ROLE) whenNotPausedNow {
        if (!(!rewardKeyUsed[idempotencyKey])) revert RewardKeyUsed();
        rewardKeyUsed[idempotencyKey] = true;
        _payReward(to, amount, reason, idempotencyKey);
    }

    /**
     * @notice Batch idempotent rewards. Reverts on any duplicate key or zero
     *         address so the whole call is atomic.
     */
    function rewardUsers(
        address[] calldata recipients,
        uint256[] calldata amounts,
        bytes32[] calldata reasons,
        uint256[] calldata idempotencyKeys
    ) external onlyRole(REWARDER_ROLE) whenNotPausedNow {
        uint256 len = recipients.length;
        if (!(len > 0)) revert EmptyBatch();
        if (!(len <= MAX_BATCH)) revert BatchTooLarge();
        if (!(amounts.length == len && reasons.length == len && idempotencyKeys.length == len)) revert LengthMismatch();
        for (uint256 i = 0; i < len; i++) {
            if (!(!rewardKeyUsed[idempotencyKeys[i]])) revert RewardKeyUsed();
            rewardKeyUsed[idempotencyKeys[i]] = true;
            _payReward(recipients[i], amounts[i], reasons[i], idempotencyKeys[i]);
        }
    }

    // =====================================================================
    // Treasury
    // =====================================================================
    /**
     * @notice Record a deposit by the caller. The caller must have approved or
     *         transferred the OPT to this contract beforehand; this call only
     *         updates accounting, it does not pull funds.
     */
    function depositOPC(uint256 amount) external nonReentrantLocal whenNotPausedNow {
        if (!(amount > 0)) revert ZeroAmount();
        if (!(balanceOf(msg.sender, OPT_TOKEN_ID) >= amount)) revert InsufficientBalance();
        depositOf[msg.sender] += amount;
        totalDeposits += amount;
        emit Deposited(msg.sender, amount);
    }

    /// @notice Withdraw a previously deposited amount back to the caller.
    function withdrawOPC(uint256 amount) external nonReentrantLocal whenNotPausedNow {
        if (!(amount > 0)) revert ZeroAmount();
        if (!(depositOf[msg.sender] >= amount)) revert ExceedsDeposit();
        depositOf[msg.sender] -= amount;
        totalWithdrawals += amount;
        _safeTransferFrom(msg.sender, msg.sender, OPT_TOKEN_ID, amount, "");
        emit Withdrawn(msg.sender, amount);
    }

    // =====================================================================
    // OryphemProxy (ORX) — router between OPT and the other assets
    // =====================================================================
    /**
     * @notice Route OPT into another asset (ORT or QTC) at the fixed proxy rate.
     *         The caller's OPT is burned and the target asset is minted to them.
     *           - 1 ORT = 50 OPT   → to buy 1 ORT you pay 50 OPT.
     *           - 1 QTC = 1000 OPT  → to buy 1 QTC you pay 1000 OPT.
     * @param assetId ORT_TOKEN_ID or QTC_TOKEN_ID.
     * @param amount  Units of the target asset to receive (must be >= 1).
     * @return optCost OPT burned to route the purchase.
     *
     * @dev This is the *proxy* entry point: it is the only sanctioned way to
     *      convert OPT into ORT/QTC. Any account may call it (self-service);
     *      the ROUTER_ROLE gate is used for the taker-side helpers below.
     */
    function swapOptFor(uint256 assetId, uint256 amount)
        external
        whenNotPausedNow
        nonReentrantLocal
        returns (uint256 optCost)
    {
        if (!(amount > 0)) revert ZeroAmount();
        if (!(assetId == ORT_TOKEN_ID || assetId == QTC_TOKEN_ID)) revert UnsupportedAsset();

        uint256 rate = assetId == ORT_TOKEN_ID ? ORT_RATE : QTC_RATE;
        optCost = rate * amount;

        // Burn the caller's OPT first (this restores OPT supply, which is
        // unlimited, so the cap is never a concern here).
        _burn(msg.sender, OPT_TOKEN_ID, optCost);

        // Mint the target asset. QTC mints respect the QTC supply cap.
        _mint(msg.sender, assetId, amount, "");

        totalOptSwappedIn += optCost;
        if (assetId == ORT_TOKEN_ID) totalOrtMinted += amount;
        else totalQtcMinted += amount;

        emit Swapped(msg.sender, msg.sender, optCost, assetId, amount);
    }

    /**
     * @notice Pay for AI usage: burn exactly 1 ORT per request from the caller
     *         and record the request. 1 request == 1 ORT.
     * @param requests Number of AI requests to purchase with ORT (>= 1).
     */
    function payAiRequest(uint256 requests) external whenNotPausedNow nonReentrantLocal {
        if (!(requests > 0)) revert ZeroRequests();
        if (!(balanceOf(msg.sender, ORT_TOKEN_ID) >= requests)) revert InsufficientORT();
        _burn(msg.sender, ORT_TOKEN_ID, requests);
        aiRequestsOf[msg.sender] += requests;
        totalAiRequests += requests;
        emit AiRequestPaid(msg.sender, requests, totalAiRequests);
    }

    /// @notice Human-readable rate table for the ORX proxy (OPT per asset unit).
    function proxyRates() external pure returns (uint256 optPerOrt, uint256 optPerQtc) {
        return (ORT_RATE, QTC_RATE);
    }

    /// @notice Supply cap for a given asset id (max uint256 = unlimited).
    function maxSupplyOf(uint256 tokenId) external pure returns (uint256) {
        if (tokenId == QTC_TOKEN_ID) return MAX_QTC_SUPPLY;
        if (tokenId == ORT_TOKEN_ID) return MAX_ORT_SUPPLY;
        return MAX_OPT_SUPPLY;
    }

    // =====================================================================
    // Mint / burn (admin)
    // =====================================================================
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

    function burn(address from, uint256 tokenId, uint256 amount)
        public
        virtual
        override
        whenNotPausedNow
    {
        if (!(from == msg.sender || isApprovedForAll(from, msg.sender))) revert NotAuthorizedToBurn();
        _burn(from, tokenId, amount);
    }

    function burnBatch(address from, uint256[] memory tokenIds, uint256[] memory amounts)
        public
        virtual
        override
        whenNotPausedNow
    {
        if (!(from == msg.sender || isApprovedForAll(from, msg.sender))) revert NotAuthorizedToBurn();
        _burnBatch(from, tokenIds, amounts);
    }

    // =====================================================================
    // Internals
    // =====================================================================
    function _payReward(address to, uint256 amount, bytes32 reason, uint256 idempotencyKey) internal {
        if (!(to != address(0))) revert ZeroRecipient();
        if (!(amount > 0)) revert ZeroAmount();
        _checkAndAccumulateDaily(OPT_TOKEN_ID, amount);
        // `_mint` → `_update` keeps `opcBalance`, `totalMinted` in sync.
        _mint(to, OPT_TOKEN_ID, amount, "");
        emit RewardPaid(to, amount, reason, idempotencyKey);
    }

    function _awardBadge(address to, uint8 badgeId) internal returns (uint256 tokenId) {
        if (!(to != address(0))) revert ZeroRecipient();
        if (!(badges[badgeId].exists)) revert BadgeNotRegistered();
        if (hasBadge[to][badgeId]) {
            return _badgeTokenId(badgeId);
        }
        hasBadge[to][badgeId] = true;
        userBadgeCount[to] += 1;
        badgeSupply[badgeId] += 1;

        tokenId = _badgeTokenId(badgeId);
        // Mint a single badge unit (id >= BADGE_TOKEN_OFFSET) as proof of the badge.
        _mint(to, tokenId, 1, "");
        emit BadgeAwarded(to, badgeId, tokenId);
    }

    function _badgeTokenId(uint8 badgeId) internal pure returns (uint256) {
        return BADGE_TOKEN_OFFSET + uint256(badgeId);
    }

    function _unlockAchievement(address account, bytes32 achievementId) internal {
        if (!(account != address(0))) revert ZeroAccount();
        if (!(achievementId != bytes32(0))) revert AchievementIdZero();
        if (!(!achievementUnlocked[account][achievementId])) revert AchievementAlreadyUnlocked();
        achievementUnlocked[account][achievementId] = true;
        achievementCount[account] += 1;
        emit AchievementUnlocked(account, achievementId);
    }

    function _checkAndAccumulateDaily(uint256 tokenId, uint256 amount) internal {
        if (!(amount > 0)) revert ZeroAmount();
        if (!(amount <= maxMintPerTx)) revert ExceedsMaxMintPerTx();

        uint256 today = block.timestamp / 1 days;
        MintWindow storage w = mintWindows[tokenId];
        if (w.day != today) {
            w.day = today;
            w.minted = 0;
        }
        if (!(w.minted + amount <= dailyMintCap)) revert ExceedsDailyCap();
        w.minted += amount;
    }

    // =====================================================================
    // ERC-1155 hooks / overrides
    // =====================================================================
    function _update(address from, address to, uint256[] memory ids, uint256[] memory values)
        internal
        override(ERC1155Upgradeable, ERC1155SupplyUpgradeable, ERC1155PausableUpgradeable)
    {
        // Block transfers of soulbound badge tokens (except mint/burn).
        if (from != address(0) && to != address(0)) {
            for (uint256 i = 0; i < ids.length; i++) {
                if (ids[i] >= BADGE_TOKEN_OFFSET) {
                    uint8 badgeId = uint8(ids[i] - BADGE_TOKEN_OFFSET);
                    if (!(!badges[badgeId].soulbound)) revert BadgeSoulbound();
                }
            }
        }

        // Enforce per-asset circulating supply caps on mints (from == 0).
        // OPT (id 0) and ORT (id 2) are unlimited; QTC (id 1) is capped at
        // MAX_QTC_SUPPLY. Burns lower `totalSupply(id)`, restoring capacity.
        if (from == address(0)) {
            for (uint256 i = 0; i < ids.length; i++) {
                if (ids[i] == QTC_TOKEN_ID) {
                    if (!(totalSupply(QTC_TOKEN_ID) + values[i] <= MAX_QTC_SUPPLY)) revert QtcSupplyExceeded();
                }
            }
        }

        // Keep the on-chain base-currency (OPT, id 0) balance mirror in sync.
        uint256 opcAmount = 0;
        for (uint256 i = 0; i < ids.length; i++) {
            if (ids[i] == OPT_TOKEN_ID) opcAmount += values[i];
        }
        if (opcAmount > 0) {
            if (from == address(0)) {
                totalMinted += opcAmount;
                if (to != address(0)) opcBalance[to] += opcAmount;
            } else if (to == address(0)) {
                totalBurned += opcAmount;
                opcBalance[from] = opcBalance[from] >= opcAmount ? opcBalance[from] - opcAmount : 0;
            } else {
                // Ordinary transfer: move the mirror balance between accounts.
                opcBalance[from] = opcBalance[from] >= opcAmount ? opcBalance[from] - opcAmount : 0;
                opcBalance[to] += opcAmount;
            }
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
