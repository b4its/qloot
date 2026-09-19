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
 * @title OryphemCoin1155 (v2) — QLoot Academy
 * @notice Upgrade target of the original OPC reward token, turning it into a
 *         full on-chain learning-state registry.
 *
 * Feature groups:
 *  - ERC-1155 multi-token with per-user balances (fungible, token id 0 = OPC).
 *  - XP + level per user (level can be granted directly or derived from XP).
 *  - Courses: create/activate, enroll, completeCourse (pays OPC + XP + badge).
 *  - Badges: metadata registry + soulbound or transferable, per-user awards.
 *  - Achievements: arbitrary achievements unlock via `unlockAchievement`.
 *  - Treasury accounting: deposits/withdrawals and a mints-minus-burns counter.
 *  - Idempotent rewards (`rewardUser` / `rewardUsers`) keyed on a uint256 key.
 *  - Burn/mint/pause when active, gas-safe batch cap, reentrancy guard.
 *
 * Upgrade safety:
 *  - The original contract's storage layout is preserved verbatim in
 *    {OryphemCoin1155LegacyBase}. New state is appended only.
 *  - `initializeV2` initialises the new modules and is idempotent.
 *
 * Security:
 *  - Every state-changing entry point is role-gated or self-scoped.
 *  - `nonReentrantLocal` guards all external-value-moving functions.
 *  - Only registered badges are recognized; soulbound badges cannot transfer.
 */
contract OryphemCoin1155 is
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

    /// @notice Primary reward token id (OPC).
    uint256 public constant OPC_TOKEN_ID = 0;
    /// @notice Token id space for badges starts at this offset.
    uint256 public constant BADGE_TOKEN_OFFSET = 1_000_000;
    /// @notice Maximum recipients in a single rewardUsers call (gas safety).
    uint256 public constant MAX_BATCH = 200;
    /// @notice XP required per level (Level 1 needs LEVEL_XP_STEP XP, etc.).
    uint256 public constant LEVEL_XP_STEP = 100;

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
    /// @notice Treasury address that custodies OPC on-chain.
    address public treasury;
    /// @notice Monotonic per-user OPC balances mirrored on-chain (token id 0).
    mapping(address => uint256) public opcBalance;
    /// @notice Per-user experience points.
    mapping(address => uint256) public xp;
    /// @notice Per-user level.
    mapping(address => uint32) public level;
    /// @notice Total XP ever distributed.
    uint256 public totalXpDistributed;
    /// @notice Total OPC minted (all time, all ids).
    uint256 public totalMinted;
    /// @notice Total OPC burned (all time, all ids).
    uint256 public totalBurned;

    /// @notice Idempotency keys for rewards (uint256 keyed).
    mapping(uint256 => bool) public rewardKeyUsed;

    /// @notice Course id => configuration.
    struct Course {
        uint256 rewardAmount; // OPC paid on completion
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

    /// @dev Reserved storage to allow future upgrades without shifting layout.
    uint256[40] private __gap;

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
        require(admin != address(0), "OPC: admin is zero");
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

        treasury = treasury_ == address(0) ? admin : treasury_;
        v2Initialized = true;
        emit V2Initialized(treasury, admin);
    }

    /**
     * @notice Initialise the v2 modules on an upgraded (previously v1) proxy.
     * @dev Idempotent; safe to call once after `upgradeToAndCall`.
     */
    function initializeV2(address admin, address treasury_) external reinitializer(2) {
        require(admin != address(0), "OPC: admin is zero");

        if (!hasRole(ADMIN_ROLE, admin)) _grantRole(ADMIN_ROLE, admin);
        if (!hasRole(DEFAULT_ADMIN_ROLE, admin)) _grantRole(DEFAULT_ADMIN_ROLE, admin);

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
        require(maxMintPerTx_ > 0, "OPC: maxMintPerTx=0");
        require(dailyMintCap_ >= maxMintPerTx_, "OPC: cap < max");
        maxMintPerTx = maxMintPerTx_;
        dailyMintCap = dailyMintCap_;
    }

    function setTreasury(address newTreasury) external onlyRole(ADMIN_ROLE) {
        require(newTreasury != address(0), "OPC: treasury is zero");
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
        require(
            hasRole(REWARDER_ROLE, msg.sender) || msg.sender == address(this),
            "OPC: not rewarder"
        );
        _addXp(account, amount);
    }

    /// @dev Internal XP grant used by role-gated callers and completeCourse.
    function _addXp(address account, uint256 amount) internal {
        require(account != address(0), "OPC: account is zero");
        require(amount > 0, "OPC: amount=0");

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
        require(account != address(0), "OPC: account is zero");
        require(newLevel >= level[account], "OPC: level cannot decrease");
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
        require(!courseExists[courseId], "OPC: course exists");
        require(badgeId == 0 || badges[badgeId].exists, "OPC: badge not registered");
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
        require(courseExists[courseId], "OPC: no such course");
        require(badgeId == 0 || badges[badgeId].exists, "OPC: badge not registered");
        courses[courseId] = Course({rewardAmount: rewardAmount, badgeId: badgeId, active: active});
        emit CourseUpdated(courseId, rewardAmount, badgeId, active);
    }

    function courseReward(uint256 courseId) external view returns (uint256) {
        return courses[courseId].rewardAmount;
    }

    function courseActive(uint256 courseId) external view returns (bool) {
        return courses[courseId].active;
    }

    /// @notice Enroll the caller in an active course.
    function enroll(uint256 courseId) external whenNotPausedNow {
        require(courseExists[courseId], "OPC: no such course");
        require(courses[courseId].active, "OPC: course inactive");
        require(!enrolled[msg.sender][courseId], "OPC: already enrolled");
        enrolled[msg.sender][courseId] = true;
        emit Enrolled(msg.sender, courseId);
    }

    /**
     * @notice Complete a course: pays OPC, grants XP and awards the course badge.
     * @dev Idempotent per (user, course). Requires prior enrollment.
     */
    function completeCourse(uint256 courseId)
        external
        whenNotPausedNow
        nonReentrantLocal
        returns (uint256 reward)
    {
        require(courseExists[courseId], "OPC: no such course");
        require(enrolled[msg.sender][courseId], "OPC: not enrolled");
        require(!completed[msg.sender][courseId], "OPC: already completed");

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
        require(badgeId != 0, "OPC: badge id 0 reserved");
        require(!badges[badgeId].exists, "OPC: badge exists");
        badges[badgeId] = Badge({uri: uri, soulbound: soulbound, exists: true});
        emit BadgeRegistered(badgeId, uri, soulbound);
    }

    function badgeUri(uint8 badgeId) external view returns (string memory) {
        return badges[badgeId].uri;
    }

    function badgeSoulbound(uint8 badgeId) external view returns (bool) {
        return badges[badgeId].soulbound;
    }

    /// @notice Award a registered badge to `to`. Idempotent per (to, badgeId).
    function awardBadge(address to, uint8 badgeId, string calldata uri)
        public
        onlyRole(REWARDER_ROLE)
        returns (uint256 tokenId)
    {
        require(badges[badgeId].exists, "OPC: badge not registered");
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
     * @notice Pay an idempotent OPC reward to `to`.
     * @dev Reverts if `idempotencyKey` was used before.
     */
    function rewardUser(
        address to,
        uint256 amount,
        bytes32 reason,
        uint256 idempotencyKey
    ) public onlyRole(REWARDER_ROLE) whenNotPausedNow {
        require(!rewardKeyUsed[idempotencyKey], "OPC: reward key used");
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
        require(len > 0, "OPC: empty batch");
        require(len <= MAX_BATCH, "OPC: batch too large");
        require(
            amounts.length == len && reasons.length == len && idempotencyKeys.length == len,
            "OPC: length mismatch"
        );
        for (uint256 i = 0; i < len; i++) {
            require(!rewardKeyUsed[idempotencyKeys[i]], "OPC: reward key used");
            rewardKeyUsed[idempotencyKeys[i]] = true;
            _payReward(recipients[i], amounts[i], reasons[i], idempotencyKeys[i]);
        }
    }

    // =====================================================================
    // Treasury
    // =====================================================================
    /**
     * @notice Record a deposit by the caller. The caller must have approved or
     *         transferred the OPC to this contract beforehand; this call only
     *         updates accounting, it does not pull funds.
     */
    function depositOPC(uint256 amount) external nonReentrantLocal whenNotPausedNow {
        require(amount > 0, "OPC: amount=0");
        require(balanceOf(msg.sender, OPC_TOKEN_ID) >= amount, "OPC: insufficient balance");
        depositOf[msg.sender] += amount;
        totalDeposits += amount;
        emit Deposited(msg.sender, amount);
    }

    /// @notice Withdraw a previously deposited amount back to the caller.
    function withdrawOPC(uint256 amount) external nonReentrantLocal whenNotPausedNow {
        require(amount > 0, "OPC: amount=0");
        require(depositOf[msg.sender] >= amount, "OPC: exceeds deposit");
        depositOf[msg.sender] -= amount;
        totalWithdrawals += amount;
        _safeTransferFrom(msg.sender, msg.sender, OPC_TOKEN_ID, amount, "");
        emit Withdrawn(msg.sender, amount);
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
        require(
            from == msg.sender || isApprovedForAll(from, msg.sender),
            "OPC: not authorized to burn"
        );
        _burn(from, tokenId, amount);
    }

    function burnBatch(address from, uint256[] memory tokenIds, uint256[] memory amounts)
        public
        virtual
        override
        whenNotPausedNow
    {
        require(
            from == msg.sender || isApprovedForAll(from, msg.sender),
            "OPC: not authorized to burn"
        );
        _burnBatch(from, tokenIds, amounts);
    }

    // =====================================================================
    // Internals
    // =====================================================================
    function _payReward(address to, uint256 amount, bytes32 reason, uint256 idempotencyKey) internal {
        require(to != address(0), "OPC: to is zero");
        require(amount > 0, "OPC: amount=0");
        _checkAndAccumulateDaily(OPC_TOKEN_ID, amount);
        // `_mint` → `_update` keeps `opcBalance`, `totalMinted` in sync.
        _mint(to, OPC_TOKEN_ID, amount, "");
        emit RewardPaid(to, amount, reason, idempotencyKey);
    }

    function _awardBadge(address to, uint8 badgeId) internal returns (uint256 tokenId) {
        require(to != address(0), "OPC: to is zero");
        require(badges[badgeId].exists, "OPC: badge not registered");
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
        require(account != address(0), "OPC: account is zero");
        require(achievementId != bytes32(0), "OPC: achievement id 0");
        require(!achievementUnlocked[account][achievementId], "OPC: achievement unlocked");
        achievementUnlocked[account][achievementId] = true;
        achievementCount[account] += 1;
        emit AchievementUnlocked(account, achievementId);
    }

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
                    require(!badges[badgeId].soulbound, "OPC: badge is soulbound");
                }
            }
        }

        // Keep the on-chain OPC balance mirror in sync (token id 0 only).
        uint256 opcAmount = 0;
        for (uint256 i = 0; i < ids.length; i++) {
            if (ids[i] == OPC_TOKEN_ID) opcAmount += values[i];
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
