// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {ReentrancyGuardTransientLocal} from "./utils/ReentrancyGuardTransientLocal.sol";

/**
 * @title OryphemAsset
 * @notice Minimal interface of an ERC-1155 Oryphem asset (OPT/QTC/ORT) used by
 *         the proxy to mint/burn the routed asset.
 */
interface IOryphemAsset {
    function routerMint(address to, uint256 amount) external;

    function routerBurn(address from, uint256 amount) external;

    function balanceOf(address account, uint256 id) external view returns (uint256);

    function ASSET_ID() external view returns (uint256);
}

/// @notice Minimal interface for the document-anchoring ability (QTC).
interface IDocumentAnchor {
    function anchorDocument(bytes32 anchorKey, bytes32 documentHash) external returns (bytes32);
}

/**
 * @title OryphemProxy (ORX) — the QLoot asset router
 * @notice Routes the network between OPT (base currency) and the other digital
 *         assets, QTC and ORT. It owns the fixed conversion rates and performs
 *         the swaps: burn OPT from the user, mint the target asset to the user.
 *
 *         Rates (OPT per 1 unit of the target asset):
 *           1 ORT = 50 OPT      (ORT_RATE)
 *           1 QTC = 1000 OPT    (QTC_RATE)
 *
 *         The proxy is granted MINTER/ROUTER powers on each asset contract so
 *         it can settle swaps. Deployed behind its own UUPS proxy, so ORX has
 *         its own contract address, separate from the assets it routes.
 */
contract OryphemProxy is
    Initializable,
    AccessControlUpgradeable,
    ReentrancyGuardTransientLocal,
    UUPSUpgradeable
{
    // =====================================================================
    // Roles
    // =====================================================================
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant ROUTER_ROLE = keccak256("ROUTER_ROLE");

    // =====================================================================
    // Rates (OPT per 1 unit of the target asset) — governable storage
    // =====================================================================
    /// @notice 1 ORT = 50 OPT (default).
    uint256 public constant ORT_RATE = 50;
    /// @notice 1 QTC = 1000 OPT (default).
    uint256 public constant QTC_RATE = 1000;

    // =====================================================================
    // Storage
    // =====================================================================
    /// @notice The OPT (base currency) ERC-1155 contract.
    IOryphemAsset public opt;
    /// @notice The QTC ERC-1155 contract.
    IOryphemAsset public qtc;
    /// @notice The ORT ERC-1155 contract.
    IOryphemAsset public ort;
    /// @notice Treasury/operator that custodies routed funds.
    address public treasury;

    /// @notice Cumulative OPT routed into the proxy.
    uint256 public totalOptSwappedIn;
    /// @notice Cumulative ORT minted through the proxy.
    uint256 public totalOrtMinted;
    /// @notice Cumulative QTC minted through the proxy.
    uint256 public totalQtcMinted;
    /// @notice Total AI requests paid in ORT.
    uint256 public totalAiRequests;

    /// @notice Live OPT-per-ORT rate (governable; WEB3-10). 0 = use default.
    uint256 public optPerOrtRate;
    /// @notice Live OPT-per-QTC rate (governable; WEB3-10). 0 = use default.
    uint256 public optPerQtcRate;

    /// @dev Reserved storage for future upgrades (reduced by 2 for the new
    ///      rate slots appended above; the layout of prior slots is unchanged,
    ///      which keeps the UUPS upgrade safe).
    uint256[38] private __gap;

    // =====================================================================
    // Events
    // =====================================================================
    event Routed(address indexed account, uint256 qtcOrOrtId, uint256 optIn, uint256 assetOut);
    event AiRequestPaid(address indexed account, uint256 requests, uint256 totalRequests);
    event AssetsUpdated(address opt, address qtc, address ort);
    event TreasuryUpdated(address oldTreasury, address newTreasury);
    /// @notice Emitted when the swap rates are changed (WEB3-10).
    event RatesUpdated(uint256 optPerOrt, uint256 optPerQtc);

    // =====================================================================
    // Errors
    // =====================================================================
    error ZeroAddress();
    error ZeroAmount();
    error UnsupportedAsset();
    error InsufficientBalance();
    error NotConfigured();

    // =====================================================================
    // Init
    // =====================================================================
    function initialize(
        address admin,
        address opt_,
        address qtc_,
        address ort_,
        address treasury_
    ) external initializer {
        if (admin == address(0)) revert ZeroAddress();
        __AccessControl_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(ROUTER_ROLE, admin);

        opt = IOryphemAsset(opt_);
        qtc = IOryphemAsset(qtc_);
        ort = IOryphemAsset(ort_);
        treasury = treasury_ == address(0) ? admin : treasury_;
        // Default rates (governable afterwards via setRates).
        optPerOrtRate = ORT_RATE;
        optPerQtcRate = QTC_RATE;
        emit AssetsUpdated(opt_, qtc_, ort_);
        emit TreasuryUpdated(address(0), treasury);
        emit RatesUpdated(optPerOrtRate, optPerQtcRate);
    }

    // =====================================================================
    // Admin
    // =====================================================================
    function setAssets(address opt_, address qtc_, address ort_) external onlyRole(ADMIN_ROLE) {
        if (opt_ == address(0) || qtc_ == address(0) || ort_ == address(0)) revert ZeroAddress();
        opt = IOryphemAsset(opt_);
        qtc = IOryphemAsset(qtc_);
        ort = IOryphemAsset(ort_);
        emit AssetsUpdated(opt_, qtc_, ort_);
    }

    function setTreasury(address newTreasury) external onlyRole(ADMIN_ROLE) {
        if (newTreasury == address(0)) revert ZeroAddress();
        emit TreasuryUpdated(treasury, newTreasury);
        treasury = newTreasury;
    }

    /**
     * @notice Update the swap rates (WEB3-10). Only ADMIN_ROLE.
     * @dev Zero falls back to the immutable default (ORT_RATE/QTC_RATE) so the
     *      contract keeps working if a rate is unset.
     */
    function setRates(uint256 optPerOrt_, uint256 optPerQtc_) external onlyRole(ADMIN_ROLE) {
        optPerOrtRate = optPerOrt_;
        optPerQtcRate = optPerQtc_;
        emit RatesUpdated(optPerOrt_, optPerQtc_);
    }

    // =====================================================================
    // Router
    // =====================================================================
    /// @notice Which asset id a target token contract is: 1 = QTC, 2 = ORT.
    function _rateFor(uint256 assetId) internal view returns (uint256) {
        if (assetId == 2) return optPerOrtRate == 0 ? ORT_RATE : optPerOrtRate;
        if (assetId == 1) return optPerQtcRate == 0 ? QTC_RATE : optPerQtcRate;
        revert UnsupportedAsset();
    }

    function _targetFor(uint256 assetId) internal view returns (IOryphemAsset) {
        if (assetId == 2) {
            if (address(ort) == address(0)) revert NotConfigured();
            return ort;
        }
        if (assetId == 1) {
            if (address(qtc) == address(0)) revert NotConfigured();
            return qtc;
        }
        revert UnsupportedAsset();
    }

    /**
     * @notice Swap OPT into QTC (assetId = 1) or ORT (assetId = 2).
     * @dev Burns `rate * amount` OPT from the caller and mints `amount` of the
     *      target asset to the caller. The proxy holds ROUTER_ROLE on each
     *      asset, so no separate ERC-1155 approval is needed.
     * @param assetId 1 = QTC, 2 = ORT.
     * @param amount  Units of the target asset to receive.
     * @return optCost OPT burned to settle the swap.
     */
    function swapOptFor(uint256 assetId, uint256 amount)
        external
        nonReentrantLocal
        returns (uint256 optCost)
    {
        if (amount == 0) revert ZeroAmount();
        uint256 rate = _rateFor(assetId);
        IOryphemAsset target = _targetFor(assetId);

        optCost = rate * amount;
        if (opt.balanceOf(msg.sender, opt.ASSET_ID()) < optCost) revert InsufficientBalance();

        // Burn OPT from the caller and mint the target asset to the caller.
        opt.routerBurn(msg.sender, optCost);
        target.routerMint(msg.sender, amount);

        totalOptSwappedIn += optCost;
        if (assetId == 2) totalOrtMinted += amount;
        else totalQtcMinted += amount;

        emit Routed(msg.sender, assetId, optCost, amount);
    }

    /**
     * @notice Pay for AI usage with ORT. 1 request == 1 ORT.
     * @dev Burns `requests` ORT from the caller via the router role.
     */
    function payAiRequest(uint256 requests) external nonReentrantLocal {
        if (requests == 0) revert ZeroAmount();
        if (address(ort) == address(0)) revert NotConfigured();
        if (ort.balanceOf(msg.sender, ort.ASSET_ID()) < requests) revert InsufficientBalance();

        ort.routerBurn(msg.sender, requests);
        totalAiRequests += requests;
        emit AiRequestPaid(msg.sender, requests, totalAiRequests);
    }

    /// @notice Current OPT-per-unit rates for ORT and QTC (governable).
    function proxyRates() external view returns (uint256 optPerOrt, uint256 optPerQtc) {
        return (
            optPerOrtRate == 0 ? ORT_RATE : optPerOrtRate,
            optPerQtcRate == 0 ? QTC_RATE : optPerQtcRate
        );
    }

    /**
     * @notice Anchor a document hash on the QTC contract (certificates).
     * @dev The proxy holds ROUTER_ROLE on QTC, so it forwards the anchoring
     *      call. Only the hash is written on-chain (no PII).
     */
    function anchorOnQtc(bytes32 anchorKey, bytes32 documentHash)
        external
        onlyRole(ROUTER_ROLE)
        returns (bytes32)
    {
        if (address(qtc) == address(0)) revert NotConfigured();
        return IDocumentAnchor(address(qtc)).anchorDocument(anchorKey, documentHash);
    }

    function _authorizeUpgrade(address) internal override onlyRole(ADMIN_ROLE) {}
}
