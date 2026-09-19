// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {OryphemCoin1155} from "../OryphemCoin1155.sol";

/**
 * @title OryphemCoin1155V2Mock
 * @notice Test-only upgrade target that demonstrates a future version bump
 *         while preserving all inherited storage. Not for production use.
 *
 * @custom:oz-upgrades-unsafe-allow missing-initializer
 * @custom:oz-upgrades-unsafe-allow constructor
 */
contract OryphemCoin1155V2Mock is OryphemCoin1155 {
    /// @notice Simple on-chain version marker for upgrade tests.
    function version() external pure returns (string memory) {
        return "v2";
    }

    /// @notice Example of a v2-only feature that reads inherited state.
    function levelAndXp(address account) external view returns (uint32, uint256) {
        return (level[account], xp[account]);
    }
}
