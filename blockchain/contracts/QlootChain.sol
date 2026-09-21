// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {OryphemAssetBase} from "./OryphemAssetBase.sol";

/**
 * @title QlootChain (QTC) — premium chain asset
 * @notice ERC-1155 premium asset used to store certificates on-chain, to hold
 *         encrypted messages (decryptable with a private key held off-chain) and
 *         other high-value operations. Obtained via the OryphemProxy (ORX) at
 *         1 QTC = 1000 OPT.
 *
 *  - ERC-1155 token id 0 = QTC.
 *  - Limited supply: capped at 1e15.
 *  - Deployed behind its own UUPS proxy → it has its own contract address.
 */
contract QlootChain is OryphemAssetBase {
    /// @notice QTC is limited: 1e15 (1_000_000_000_000_000).
    uint256 public constant QTC_MAX_SUPPLY = 1_000_000_000_000_000;

    /**
     * @notice Initialise a fresh QTC proxy.
     * @param name_   e.g. "QlootChain"
     * @param symbol_ e.g. "QTC"
     * @param uri_    ERC-1155 metadata base URI
     * @param admin   receives every role
     */
    function initialize(
        string memory name_,
        string memory symbol_,
        string memory uri_,
        address admin
    ) external initializer {
        __OryphemAsset_init(name_, symbol_, uri_, admin, QTC_MAX_SUPPLY);
    }
}
