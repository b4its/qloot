// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title IOryphemAsset
 * @notice External interface of a QLoot ERC-1155 digital asset
 *         (OPT = OryphemToken, QTC = QlootChain, ORT = OryphemIntelligence).
 *
 * Each asset is its own ERC-1155 contract using token id 0.
 */
interface IOryphemAsset {
    function name() external view returns (string memory);

    function symbol() external view returns (string memory);

    function ASSET_ID() external view returns (uint256);

    function balanceOf(address account, uint256 id) external view returns (uint256);

    function totalSupply(uint256 id) external view returns (uint256);

    function totalMinted() external view returns (uint256);

    function totalBurned() external view returns (uint256);

    /// @notice Circulating-supply cap (0 = unlimited).
    function maxSupply() external view returns (uint256);

    function mint(address to, uint256 amount) external;

    function mintBatch(address[] calldata recipients, uint256[] calldata amounts) external;

    function burn(address from, uint256 amount) external;

    function rewardUser(
        address to,
        uint256 amount,
        bytes32 reason,
        uint256 idempotencyKey
    ) external;

    function routerMint(address to, uint256 amount) external;

    function routerBurn(address from, uint256 amount) external;

    function pause() external;

    function unpause() external;
}

/**
 * @title IOryphemProxy
 * @notice External interface of the OryphemProxy (ORX) router that governs the
 *         network between OPT and the other assets.
 *
 * Rates (OPT per 1 unit of the target asset): 1 ORT = 50 OPT, 1 QTC = 1000 OPT.
 * The router asset ids are 1 = QTC, 2 = ORT.
 */
interface IOryphemProxy {
    function opt() external view returns (address);

    function qtc() external view returns (address);

    function ort() external view returns (address);

    function treasury() external view returns (address);

    function ORT_RATE() external view returns (uint256);

    function QTC_RATE() external view returns (uint256);

    function proxyRates() external view returns (uint256 optPerOrt, uint256 optPerQtc);

    /// @notice Swap OPT into QTC (assetId=1) or ORT (assetId=2).
    function swapOptFor(uint256 assetId, uint256 amount) external returns (uint256 optCost);

    /// @notice Pay for AI usage with ORT (1 request = 1 ORT).
    function payAiRequest(uint256 requests) external;

    function totalOptSwappedIn() external view returns (uint256);

    function totalOrtMinted() external view returns (uint256);

    function totalQtcMinted() external view returns (uint256);

    function totalAiRequests() external view returns (uint256);
}
