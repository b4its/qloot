// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {OryphemToken} from "../OryphemToken.sol";

/**
 * @title OryphemTokenV2Mock
 * @notice Test-only upgrade target that adds a version marker while preserving
 *         storage. Not for production use.
 *
 * @custom:oz-upgrades-unsafe-allow missing-initializer
 * @custom:oz-upgrades-unsafe-allow constructor
 */
contract OryphemTokenV2Mock is OryphemToken {
    function version() external pure returns (string memory) {
        return "v2";
    }
}
