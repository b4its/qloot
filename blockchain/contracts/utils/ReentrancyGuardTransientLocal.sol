// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title ReentrancyGuardTransientLocal
 * @notice Minimal upgrade-safe reentrancy guard backed by EIP-1153 transient
 *         storage. It consumes no persistent storage slots, so it can be used
 *         by an upgradeable contract without affecting its storage layout.
 *
 * Requires the Cancun EVM (transient storage), which the QLoot contracts target.
 */
abstract contract ReentrancyGuardTransientLocal {
    /// @dev keccak256("qloot.reentrancyguard.entered")
    bytes32 private constant _ENTERED_SLOT =
        0x2f1e6b7a54e8f2d31f76f2a4b0a6a3f3f1f0d3faca11c7b62a9bd4c0e5a1c9f2;

    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;

    error ReentrancyGuardReentrantCall();

    modifier nonReentrantLocal() {
        _nonReentrantBefore();
        _;
        _nonReentrantAfter();
    }

    function _nonReentrantBefore() private {
        uint256 status = _tload(_ENTERED_SLOT);
        if (status == _ENTERED) revert ReentrancyGuardReentrantCall();
        _tstore(_ENTERED_SLOT, _ENTERED);
    }

    function _nonReentrantAfter() private {
        _tstore(_ENTERED_SLOT, _NOT_ENTERED);
    }

    function _tload(bytes32 slot) private view returns (uint256 value) {
        assembly ("memory-safe") {
            value := tload(slot)
        }
    }

    function _tstore(bytes32 slot, uint256 value) private {
        assembly ("memory-safe") {
            tstore(slot, value)
        }
    }
}
