// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title IQLootAcademy
 * @notice External interface of the upgraded OryphemCoin1155 (v2) contract.
 *
 * The v2 contract evolves the original ERC-1155 reward token into a full
 * on-chain learning-state registry for QLoot: per-user OPC balances, XP and
 * levels, courses and enrollment, badges, achievements and treasury accounting.
 */
interface IQLootAcademy {
    // ---------------------------- balances / supply ----------------------
    function balanceOf(address account, uint256 id) external view returns (uint256);

    function totalSupply(uint256 id) external view returns (uint256);

    function totalMinted(uint256 tokenId) external view returns (uint256);

    function totalBurned(uint256 tokenId) external view returns (uint256);

    // ---------------------------- XP / level -----------------------------
    function xp(address account) external view returns (uint256);

    function level(address account) external view returns (uint32);

    function addXp(address account, uint256 amount) external;

    function setLevel(address account, uint32 newLevel) external;

    function totalXpDistributed() external view returns (uint256);

    // ---------------------------- courses --------------------------------
    function createCourse(uint256 courseId, uint256 rewardAmount, uint8 badgeId, bool active) external;

    function setCourse(
        uint256 courseId,
        uint256 rewardAmount,
        uint8 badgeId,
        bool active
    ) external;

    function courseReward(uint256 courseId) external view returns (uint256);

    function courseActive(uint256 courseId) external view returns (bool);

    function enrolled(address account, uint256 courseId) external view returns (bool);

    function completed(address account, uint256 courseId) external view returns (bool);

    function enroll(uint256 courseId) external;

    function completeCourse(uint256 courseId) external returns (uint256 reward);

    function courseCompletionCount(uint256 courseId) external view returns (uint256);

    // ---------------------------- badges / achievements ------------------
    function awardBadge(address to, uint8 badgeId, string calldata uri) external returns (uint256 tokenId);

    function hasBadge(address account, uint8 badgeId) external view returns (bool);

    function userBadgeCount(address account) external view returns (uint256);

    function registerBadge(uint8 badgeId, string calldata uri, bool soulbound) external;

    function badgeUri(uint8 badgeId) external view returns (string memory);

    function badgeSoulbound(uint8 badgeId) external view returns (bool);

    // ---------------------------- rewards ---------------------------------
    function rewardUser(
        address to,
        uint256 amount,
        bytes32 reason,
        uint256 idempotencyKey
    ) external;

    function rewardUsers(
        address[] calldata recipients,
        uint256[] calldata amounts,
        bytes32[] calldata reasons,
        uint256[] calldata idempotencyKeys
    ) external;

    function rewardKeyUsed(uint256 key) external view returns (bool);

    // ---------------------------- treasury --------------------------------
    function treasury() external view returns (address);

    function depositOPC(uint256 amount) external;

    function withdrawOPC(uint256 amount) external;

    function depositOf(address account) external view returns (uint256);

    function totalDeposits() external view returns (uint256);

    function totalWithdrawals() external view returns (uint256);
}
