// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {OryphemAssetBase} from "./OryphemAssetBase.sol";

/**
 * @title OryphemIntelligence (ORT) — AI-service credit
 * @notice ERC-1155 asset used as the entitlement to use QLoot's AI services
 *         ("bertanya ke QLO"). 1 AI request costs exactly 1 ORT. Obtained via
 *         the OryphemProxy (ORX) at 1 ORT = 50 OPT.
 *
 *  - ERC-1155 token id 0 = ORT.
 *  - Supply is minted on demand (no hard cap).
 *  - Deployed behind its own UUPS proxy → it has its own contract address.
 */
contract OryphemIntelligence is OryphemAssetBase {
    /**
     * @notice Initialise a fresh ORT proxy.
     * @param name_   e.g. "OryphemIntelligence"
     * @param symbol_ e.g. "ORT"
     * @param uri_    ERC-1155 metadata base URI
     * @param admin   receives every role
     */
    function initialize(
        string memory name_,
        string memory symbol_,
        string memory uri_,
        address admin
    ) external initializer {
        // No hard cap.
        __OryphemAsset_init(name_, symbol_, uri_, admin, 0);
    }
}
