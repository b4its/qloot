const { expect } = require("chai");
const { ethers } = require("hardhat");

const OPC_TOKEN_ID = 0n;
const ZERO = ethers.ZeroAddress;
const ZERO_HASH = ethers.ZeroHash;

// Helper: keccak over concat of parts (mirrors the off-chain reward key calc).
function rewardKey(parts) {
  return ethers.keccak256(
    ethers.concat(parts.map((p) => (typeof p === "string" ? ethers.toUtf8Bytes(p) : p)))
  );
}

describe("OryphemCoin1155", function () {
  let opc;
  let admin, minter, rewarder, pauser, uriManager, alice, bob, attacker;
  let treasury;

  const MINTER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("MINTER_ROLE"));
  const REWARDER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("REWARDER_ROLE"));
  const PAUSER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("PAUSER_ROLE"));
  const URI_MANAGER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("URI_MANAGER_ROLE"));

  beforeEach(async function () {
    [admin, minter, rewarder, pauser, uriManager, alice, bob, attacker, treasury] =
      await ethers.getSigners();

    const Factory = await ethers.getContractFactory("OryphemCoin1155");
    opc = await Factory.deploy(
      "OryphemCoin",
      "OPC",
      "https://metadata.qloot.example/opc/{id}.json",
      admin.address
    );
    await opc.waitForDeployment();

    await opc.connect(admin).grantRole(MINTER_ROLE, minter.address);
    await opc.connect(admin).grantRole(REWARDER_ROLE, rewarder.address);
    await opc.connect(admin).grantRole(PAUSER_ROLE, pauser.address);
    await opc.connect(admin).grantRole(URI_MANAGER_ROLE, uriManager.address);
  });

  describe("metadata", function () {
    it("exposes name, symbol and uri", async function () {
      expect(await opc.name()).to.equal("OryphemCoin");
      expect(await opc.symbol()).to.equal("OPC");
      expect(await opc.uri(OPC_TOKEN_ID)).to.equal(
        "https://metadata.qloot.example/opc/{id}.json"
      );
    });

    it("only uri manager can set uri and it emits MetadataPublished", async function () {
      await expect(opc.connect(attacker).setURI("x")).to.be.reverted;
      await expect(opc.connect(uriManager).setURI("ipfs://new/"))
        .to.emit(opc, "MetadataPublished")
        .withArgs("ipfs://new/", uriManager.address);
      expect(await opc.uri(0)).to.equal("ipfs://new/");
    });
  });

  describe("roles", function () {
    it("admin has default admin role", async function () {
      const DEFAULT_ADMIN = ZERO_HASH;
      expect(await opc.hasRole(DEFAULT_ADMIN, admin.address)).to.equal(true);
    });

    it("rejects mint from non-minter", async function () {
      await expect(
        opc.connect(attacker).mint(alice.address, OPC_TOKEN_ID, 1n, "0x")
      ).to.be.reverted;
    });

    it("rejects reward from non-rewarder", async function () {
      await expect(
        opc
          .connect(attacker)
          .recordReward(
            rewardKey(["q1"]),
            rewardKey(["quest"]),
            rewardKey(["u"]),
            1,
            treasury.address,
            OPC_TOKEN_ID,
            10n
          )
      ).to.be.reverted;
    });
  });

  describe("minting", function () {
    it("minter can mint and supply is tracked", async function () {
      await opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, 100n, "0x");
      expect(await opc.balanceOf(treasury.address, OPC_TOKEN_ID)).to.equal(100n);
      expect(await opc["totalSupply(uint256)"](OPC_TOKEN_ID)).to.equal(100n);
    });

    it("enforces maxMintPerTx", async function () {
      const max = await opc.maxMintPerTx();
      await expect(
        opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, max + 1n, "0x")
      ).to.be.revertedWith("OPC: exceeds maxMintPerTx");
    });

    it("enforces the rolling daily cap", async function () {
      await opc.connect(admin).setLimits(1_000_000n, 1_500_000n);
      await opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, 1_000_000n, "0x");
      await expect(
        opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, 1_000_000n, "0x")
      ).to.be.revertedWith("OPC: exceeds daily cap");
    });

    it("rejects zero amount", async function () {
      await expect(
        opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, 0n, "0x")
      ).to.be.revertedWith("OPC: amount=0");
    });

    it("mintBatch mints multiple ids and tracks supply", async function () {
      await opc
        .connect(minter)
        .mintBatch(treasury.address, [0n, 1n], [70n, 30n], "0x");
      expect(await opc.balanceOf(treasury.address, 0n)).to.equal(70n);
      expect(await opc.balanceOf(treasury.address, 1n)).to.equal(30n);
      expect(await opc["totalSupply(uint256)"](0n)).to.equal(70n);
      expect(await opc["totalSupply(uint256)"](1n)).to.equal(30n);
    });

    it("mintBatch enforces the per-tx cap per entry", async function () {
      const max = await opc.maxMintPerTx();
      await expect(
        opc.connect(minter).mintBatch(treasury.address, [0n], [max + 1n], "0x")
      ).to.be.revertedWith("OPC: exceeds maxMintPerTx");
    });

    it("setLimits emits LimitsUpdated", async function () {
      await expect(opc.connect(admin).setLimits(500n, 5000n))
        .to.emit(opc, "LimitsUpdated")
        .withArgs(500n, 5000n);
    });

    it("only admin can change limits and cap must be >= max", async function () {
      await expect(opc.connect(attacker).setLimits(1n, 1n)).to.be.reverted;
      await expect(
        opc.connect(admin).setLimits(100n, 50n)
      ).to.be.revertedWith("OPC: cap < max");
    });
  });

  describe("recordReward idempotency", function () {
    it("records a reward once and emits both events", async function () {
      const rKey = rewardKey(["quest:1", "user:1", "rank:1", "v1"]);
      const qRef = rewardKey(["quest:1"]);
      const uRef = rewardKey(["user:1"]);

      await expect(
        opc
          .connect(rewarder)
          .recordReward(
            rKey,
            qRef,
            uRef,
            1,
            treasury.address,
            OPC_TOKEN_ID,
            100n
          )
      )
        .to.emit(opc, "RewardGranted")
        .withArgs(rKey, uRef, OPC_TOKEN_ID, 100n, treasury.address)
        .and.to.emit(opc, "QuestRewardFinalized");

      expect(await opc.rewardFinalized(rKey)).to.equal(true);
      expect(await opc.balanceOf(treasury.address, OPC_TOKEN_ID)).to.equal(100n);
    });

    it("rejects duplicate reward key", async function () {
      const rKey = rewardKey(["dup"]);
      const args = [
        rKey,
        rewardKey(["q"]),
        rewardKey(["u"]),
        1,
        treasury.address,
        OPC_TOKEN_ID,
        10n,
      ];
      await opc.connect(rewarder).recordReward(...args);
      await expect(opc.connect(rewarder).recordReward(...args)).to.be.revertedWith(
        "OPC: reward already finalized"
      );
    });

    it("batch records three winners atomically", async function () {
      const keys = [
        rewardKey(["q", "u1"]),
        rewardKey(["q", "u2"]),
        rewardKey(["q", "u3"]),
      ];
      const quests = [rewardKey(["q"]), rewardKey(["q"]), rewardKey(["q"])];
      const users = [rewardKey(["u1"]), rewardKey(["u2"]), rewardKey(["u3"])];
      const ranks = [1, 2, 3];
      const amounts = [100n, 60n, 40n];

      await expect(
        opc
          .connect(rewarder)
          .recordRewards(keys, quests, users, ranks, treasury.address, OPC_TOKEN_ID, amounts)
      ).to.emit(opc, "RewardGranted");

      expect(await opc["totalSupply(uint256)"](OPC_TOKEN_ID)).to.equal(200n);
      expect(await opc.rewardFinalized(keys[0])).to.equal(true);
      expect(await opc.rewardFinalized(keys[2])).to.equal(true);
    });

    it("batch rejects mismatched array lengths", async function () {
      await expect(
        opc
          .connect(rewarder)
          .recordRewards(
            [rewardKey(["a"])],
            [],
            [],
            [],
            treasury.address,
            OPC_TOKEN_ID,
            [1n]
          )
      ).to.be.revertedWith("OPC: length mismatch");
    });

    it("batch rejects a duplicate key in the same call", async function () {
      const k = rewardKey(["same"]);
      await expect(
        opc
          .connect(rewarder)
          .recordRewards(
            [k, k],
            [rewardKey(["q"]), rewardKey(["q"])],
            [rewardKey(["u"]), rewardKey(["u"])],
            [1, 2],
            treasury.address,
            OPC_TOKEN_ID,
            [10n, 10n]
          )
      ).to.be.revertedWith("OPC: reward already finalized");
    });
  });

  describe("custodial + withdrawal events", function () {
    it("records custodial allocation", async function () {
      const uRef = rewardKey(["u1"]);
      await expect(
        opc.connect(rewarder).recordCustodialAllocation(uRef, OPC_TOKEN_ID, 25n, treasury.address)
      )
        .to.emit(opc, "CustodialAllocation")
        .withArgs(uRef, OPC_TOKEN_ID, 25n, treasury.address);
    });

    it("records withdrawal request", async function () {
      const wRef = rewardKey(["w1"]);
      const uRef = rewardKey(["u1"]);
      await expect(
        opc.connect(rewarder).recordWithdrawalRequested(wRef, uRef, alice.address, OPC_TOKEN_ID, 5n)
      )
        .to.emit(opc, "WithdrawalRequested")
        .withArgs(wRef, uRef, alice.address, OPC_TOKEN_ID, 5n);
    });

    it("completes withdrawal by transferring treasury tokens", async function () {
      // Treasury holds tokens (simulate the platform minter as treasury operator).
      await opc.connect(minter).mint(minter.address, OPC_TOKEN_ID, 50n, "0x");
      const wRef = rewardKey(["w2"]);
      await expect(
        opc.connect(minter).completeWithdrawal(wRef, alice.address, OPC_TOKEN_ID, 20n)
      )
        .to.emit(opc, "WithdrawalCompleted")
        .withArgs(wRef, alice.address, OPC_TOKEN_ID, 20n, minter.address);
      expect(await opc.balanceOf(alice.address, OPC_TOKEN_ID)).to.equal(20n);
    });
  });

  describe("pause", function () {
    it("pauser can pause and transfers are blocked", async function () {
      await opc.connect(minter).mint(minter.address, OPC_TOKEN_ID, 10n, "0x");
      await opc.connect(pauser).pause();

      await expect(
        opc
          .connect(minter)
          .safeTransferFrom(minter.address, alice.address, OPC_TOKEN_ID, 1n, "0x")
      ).to.be.reverted;

      await opc.connect(pauser).unpause();
      await opc
        .connect(minter)
        .safeTransferFrom(minter.address, alice.address, OPC_TOKEN_ID, 1n, "0x");
      expect(await opc.balanceOf(alice.address, OPC_TOKEN_ID)).to.equal(1n);
    });

    it("non-pauser cannot pause", async function () {
      await expect(opc.connect(attacker).pause()).to.be.reverted;
    });

    it("paused blocks minting", async function () {
      await opc.connect(pauser).pause();
      await expect(
        opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, 1n, "0x")
      ).to.be.reverted;
      await opc.connect(pauser).unpause();
      await opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, 1n, "0x");
      expect(await opc.balanceOf(treasury.address, OPC_TOKEN_ID)).to.equal(1n);
    });
  });

  describe("burn", function () {
    it("holder can burn their tokens and supply decreases", async function () {
      await opc.connect(minter).mint(alice.address, OPC_TOKEN_ID, 30n, "0x");
      await opc.connect(alice).burn(alice.address, OPC_TOKEN_ID, 10n);
      expect(await opc.balanceOf(alice.address, OPC_TOKEN_ID)).to.equal(20n);
      expect(await opc["totalSupply(uint256)"](OPC_TOKEN_ID)).to.equal(20n);
    });
  });

  describe("supportsInterface", function () {
    it("supports ERC-1155 and AccessControl", async function () {
      expect(await opc.supportsInterface("0xd9b67a26")).to.equal(true); // ERC-1155
      expect(await opc.supportsInterface("0x7965db0b")).to.equal(true); // AccessControl
    });
  });

  describe("fuzz: daily cap invariant", function () {
    it("never lets cumulative mint exceed the daily cap", async function () {
      await opc.connect(admin).setLimits(1000n, 5000n);
      const amounts = [1000n, 1000n, 1000n, 1000n, 1000n];
      for (const a of amounts) {
        await opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, a, "0x");
      }
      await expect(
        opc.connect(minter).mint(treasury.address, OPC_TOKEN_ID, 1n, "0x")
      ).to.be.revertedWith("OPC: exceeds daily cap");
      expect(await opc["totalSupply(uint256)"](OPC_TOKEN_ID)).to.equal(5000n);
    });
  });
});
