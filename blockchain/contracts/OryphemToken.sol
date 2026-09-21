// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {OryphemAssetBase} from "./OryphemAssetBase.sol";

/**
 * @title OryphemToken (OPT) — QLoot base currency
 * @notice ERC-1155 asset obtained inside the QLoot system. It is the base unit
 *         every reward is paid in and the reserve the OryphemProxy (ORX) router
 *         converts into QTC / ORT.
 *
 *  - ERC-1155 token id 0 = OPT.
 *  - Unlimited supply (base currency).
 *  - Deployed behind its own UUPS proxy → it has its own contract address.
 */
contract OryphemToken is OryphemAssetBase {
    /**
     * @notice Initialise a fresh OPT proxy.
     * @param name_   e.g. "OryphemToken"
     * @param symbol_ e.g. "OPT"
     * @param uri_    ERC-1155 metadata base URI
     * @param admin   receives every role
     */
    function initialize(
        string memory name_,
        string memory symbol_,
        string memory uri_,
        address admin
    ) external initializer {
        // Unlimited supply: maxSupply = 0.
        __OryphemAsset_init(name_, symbol_, uri_, admin, 0);
    }
}
