const { expect } = require("chai");
const { ethers, upgrades } = require("hardhat");

const OPC = 0n;
const BADGE_OFFSET = 1_000_000n;
const MAX_BATCH = 200n;
const LEVEL_STEP = 100n;

const ZERO = ethers.ZeroAddress;
const ZERO_HASH = ethers.ZeroHash;

const role = (name) => ethers.keccak256(ethers.toUtf8Bytes(name));
const MINTER = role("MINTER_ROLE");
const REWARDER = role("REWARDER_ROLE");
const PAUSER = role("PAUSER_ROLE");
const URI_MANAGER = role("URI_MANAGER_ROLE");
const ADMIN = role("ADMIN_ROLE");
const DEFAULT_ADMIN = ZERO_HASH;

/**
 * Deploys OryphemCoin behind a UUPS proxy via hardhat-upgrades and wires
 * up the common roles used across the suite.
 */
async function deployFixture() {
  const [
    deployer,
    admin,
    minter,
    rewarder,
    pauser,
    uriManager,
    alice,
    bob,
    carol,
    attacker,
    treasury,
  ] = await ethers.getSigners();

  const Factory = await ethers.getContractFactory("OryphemCoin");
  const opc = await upgrades.deployProxy(
    Factory,
    [
      "OryphemCoin",
      "OPC",
      "https://metadata.qloot.example/opc/{id}.json",
      admin.address,
      treasury.address,
    ],
    { kind: "uups", initializer: "initialize" }
  );
  await opc.waitForDeployment();

  await opc.connect(admin).grantRole(MINTER, minter.address);
  await opc.connect(admin).grantRole(REWARDER, rewarder.address);
  await opc.connect(admin).grantRole(PAUSER, pauser.address);
  await opc.connect(admin).grantRole(URI_MANAGER, uriManager.address);

  return {
    opc,
    deployer,
    admin,
    minter,
    rewarder,
    pauser,
    uriManager,
    alice,
    bob,
    carol,
    attacker,
    treasury,
  };
}

describe("OryphemCoin v2 — QLoot Academy", function () {
  let opc, admin, minter, rewarder, pauser, uriManager, alice, bob, carol, attacker, treasury;

  beforeEach(async function () {
    ({ opc, admin, minter, rewarder, pauser, uriManager, alice, bob, carol, attacker, treasury } =
      await deployFixture());
  });

  // =====================================================================
  describe("initialization & metadata", function () {
    it("sets name, symbol, uri and treasury", async function () {
      expect(await opc.name()).to.equal("OryphemCoin");
      expect(await opc.symbol()).to.equal("OPC");
      expect(await opc.uri(OPC)).to.equal("https://metadata.qloot.example/opc/{id}.json");
      expect(await opc.treasury()).to.equal(treasury.address);
    });

    it("grants the full role set to the admin", async function () {
      for (const r of [DEFAULT_ADMIN, ADMIN, MINTER, REWARDER, PAUSER, URI_MANAGER]) {
        expect(await opc.hasRole(r, admin.address)).to.equal(true);
      }
    });

    it("rejects re-initialization", async function () {
      await expect(
        opc.initialize("x", "y", "z", admin.address, treasury.address)
      ).to.be.revertedWithCustomError(opc, "InvalidInitialization");
    });

    it("only uri manager can set uri", async function () {
      await expect(opc.connect(attacker).setURI("x")).to.be.reverted;
      await opc.connect(uriManager).setURI("ipfs://new/");
      expect(await opc.uri(0)).to.equal("ipfs://new/");
    });

    it("only admin can set treasury", async function () {
      await expect(opc.connect(attacker).setTreasury(alice.address)).to.be.reverted;
      await opc.connect(admin).setTreasury(alice.address);
      expect(await opc.treasury()).to.equal(alice.address);
      await expect(opc.connect(admin).setTreasury(ZERO)).to.be.revertedWith(
        "OPC: treasury is zero"
      );
    });
  });

  // =====================================================================
  describe("limits & minting", function () {
    it("mints and tracks supply", async function () {
      await opc.connect(minter).mint(treasury.address, OPC, 100n, "0x");
      expect(await opc.balanceOf(treasury.address, OPC)).to.equal(100n);
      expect(await opc["totalSupply(uint256)"](OPC)).to.equal(100n);
      expect(await opc.totalMinted()).to.equal(100n);
    });

    it("exposes the coin max supply constant (1e20)", async function () {
      expect(await opc.MAX_OPC_SUPPLY()).to.equal(100_000_000_000_000_000_000n);
    });

    it("caps the circulating OPC supply at MAX_OPC_SUPPLY", async function () {
      const cap = await opc.MAX_OPC_SUPPLY();
      // Raise the per-tx/daily limits so the cap itself is the binding limit.
      await opc.connect(admin).setLimits(cap, cap);

      await opc.connect(minter).mint(treasury.address, OPC, cap, "0x");
      expect(await opc["totalSupply(uint256)"](OPC)).to.equal(cap);

      // Move to a new day so the rolling daily cap resets, isolating the
      // supply cap as the reason for the next failure.
      await ethers.provider.send("evm_increaseTime", [24 * 60 * 60 + 1]);
      await ethers.provider.send("evm_mine", []);

      await expect(opc.connect(minter).mint(treasury.address, OPC, 1n, "0x")).to.be.revertedWith(
        "OPC: max supply exceeded"
      );
    });

    it("burning frees supply capacity again", async function () {
      const cap = await opc.MAX_OPC_SUPPLY();
      await opc.connect(admin).setLimits(cap, cap);
      // Mint to the admin so it can burn its own coins.
      await opc.connect(minter).mint(admin.address, OPC, cap, "0x");

      await opc.connect(admin).burn(admin.address, OPC, 1_000n);
      expect(await opc["totalSupply(uint256)"](OPC)).to.equal(cap - 1_000n);

      // Reset the daily window, then the burned amount can be minted again.
      await ethers.provider.send("evm_increaseTime", [24 * 60 * 60 + 1]);
      await ethers.provider.send("evm_mine", []);
      await opc.connect(minter).mint(admin.address, OPC, 1_000n, "0x");
      expect(await opc["totalSupply(uint256)"](OPC)).to.equal(cap);
    });

    it("does not cap badge (non-coin) ids", async function () {
      await opc.connect(admin).registerBadge(7, "ipfs://badge/7", false);
      // Badge ids are outside the coin cap; minting 1 unit is unaffected.
      await opc.connect(minter).mint(alice.address, BADGE_OFFSET + 7n, 1n, "0x");
      expect(await opc.balanceOf(alice.address, BADGE_OFFSET + 7n)).to.equal(1n);
    });

    it("enforces maxMintPerTx", async function () {
      const max = await opc.maxMintPerTx();
      await expect(
        opc.connect(minter).mint(treasury.address, OPC, max + 1n, "0x")
      ).to.be.revertedWith("OPC: exceeds maxMintPerTx");
    });

    it("enforces the rolling daily cap", async function () {
      await opc.connect(admin).setLimits(1_000_000n, 1_500_000n);
      await opc.connect(minter).mint(treasury.address, OPC, 1_000_000n, "0x");
      await expect(
        opc.connect(minter).mint(treasury.address, OPC, 1_000_000n, "0x")
      ).to.be.revertedWith("OPC: exceeds daily cap");
    });

    it("only admin can setLimits and cap >= max", async function () {
      await expect(opc.connect(attacker).setLimits(1n, 2n)).to.be.reverted;
      await expect(opc.connect(admin).setLimits(100n, 50n)).to.be.revertedWith("OPC: cap < max");
    });

    it("mintBatch works and respects per-entry cap", async function () {
      await opc.connect(minter).mintBatch(treasury.address, [0n, 1n], [70n, 30n], "0x");
      expect(await opc.balanceOf(treasury.address, 0n)).to.equal(70n);
      expect(await opc.balanceOf(treasury.address, 1n)).to.equal(30n);
      const max = await opc.maxMintPerTx();
      await expect(
        opc.connect(minter).mintBatch(treasury.address, [0n], [max + 1n], "0x")
      ).to.be.revertedWith("OPC: exceeds maxMintPerTx");
    });
  });

  // =====================================================================
  describe("XP & level", function () {
    it("computes level from XP", async function () {
      expect(await opc.levelFromXp(0n)).to.equal(1n);
      expect(await opc.levelFromXp(99n)).to.equal(1n);
      expect(await opc.levelFromXp(100n)).to.equal(2n);
      expect(await opc.levelFromXp(250n)).to.equal(3n);
    });

    it("adds XP and raises the level", async function () {
      await opc.connect(rewarder).addXp(alice.address, 250n);
      expect(await opc.xp(alice.address)).to.equal(250n);
      expect(await opc.level(alice.address)).to.equal(3n);
      expect(await opc.totalXpDistributed()).to.equal(250n);
    });

    it("only rewarder can add XP directly", async function () {
      await expect(opc.connect(alice).addXp(alice.address, 10n)).to.be.revertedWith(
        "OPC: not rewarder"
      );
    });

    it("admin can set a higher level but not lower", async function () {
      await opc.connect(admin).setLevel(alice.address, 5n);
      expect(await opc.level(alice.address)).to.equal(5n);
      await expect(opc.connect(admin).setLevel(alice.address, 2n)).to.be.revertedWith(
        "OPC: level cannot decrease"
      );
    });
  });

  // =====================================================================
  describe("badges", function () {
    beforeEach(async function () {
      await opc.connect(admin).registerBadge(1, "ipfs://badge1", false);
      await opc.connect(admin).registerBadge(2, "ipfs://badge2", true); // soulbound
    });

    it("registers badges and reads metadata", async function () {
      expect(await opc.badgeUri(1)).to.equal("ipfs://badge1");
      expect(await opc.badgeSoulbound(2)).to.equal(true);
    });

    it("rejects badge id 0 and duplicates", async function () {
      await expect(opc.connect(admin).registerBadge(0, "x", false)).to.be.revertedWith(
        "OPC: badge id 0 reserved"
      );
      await expect(opc.connect(admin).registerBadge(1, "x", false)).to.be.revertedWith(
        "OPC: badge exists"
      );
    });

    it("awards a badge once and mints a proof token", async function () {
      await opc.connect(rewarder).awardBadge(alice.address, 1, "");
      expect(await opc.hasBadge(alice.address, 1)).to.equal(true);
      expect(await opc.userBadgeCount(alice.address)).to.equal(1n);
      expect(await opc.badgeSupply(1)).to.equal(1n);
      const tokenId = BADGE_OFFSET + 1n;
      expect(await opc.balanceOf(alice.address, tokenId)).to.equal(1n);

      // second award is a no-op
      await opc.connect(rewarder).awardBadge(alice.address, 1, "");
      expect(await opc.badgeSupply(1)).to.equal(1n);
      expect(await opc.userBadgeCount(alice.address)).to.equal(1n);
    });

    it("cannot award an unregistered badge", async function () {
      await expect(opc.connect(rewarder).awardBadge(alice.address, 9, "")).to.be.revertedWith(
        "OPC: badge not registered"
      );
    });

    it("only admin can register, only rewarder can award", async function () {
      await expect(opc.connect(attacker).registerBadge(3, "x", false)).to.be.reverted;
      await expect(opc.connect(attacker).awardBadge(alice.address, 1, "")).to.be.reverted;
    });

    it("blocks transfer of soulbound badges but allows transferable ones", async function () {
      await opc.connect(rewarder).awardBadge(alice.address, 1, ""); // transferable
      await opc.connect(rewarder).awardBadge(alice.address, 2, ""); // soulbound
      // transferable badge can move
      await opc
        .connect(alice)
        .safeTransferFrom(alice.address, bob.address, BADGE_OFFSET + 1n, 1n, "0x");
      // soulbound badge cannot
      await expect(
        opc.connect(alice).safeTransferFrom(alice.address, bob.address, BADGE_OFFSET + 2n, 1n, "0x")
      ).to.be.revertedWith("OPC: badge is soulbound");
    });
  });

  // =====================================================================
  describe("achievements", function () {
    it("unlocks an achievement once", async function () {
      const id = ethers.keccak256(ethers.toUtf8Bytes("first_login"));
      await opc.connect(rewarder).unlockAchievement(alice.address, id);
      expect(await opc.achievementUnlocked(alice.address, id)).to.equal(true);
      expect(await opc.achievementCount(alice.address)).to.equal(1n);
      await expect(opc.connect(rewarder).unlockAchievement(alice.address, id)).to.be.revertedWith(
        "OPC: achievement unlocked"
      );
    });

    it("rejects zero id / zero account and non-rewarder", async function () {
      const id = ethers.keccak256(ethers.toUtf8Bytes("x"));
      await expect(
        opc.connect(rewarder).unlockAchievement(alice.address, ZERO_HASH)
      ).to.be.revertedWith("OPC: achievement id 0");
      await expect(opc.connect(rewarder).unlockAchievement(ZERO, id)).to.be.revertedWith(
        "OPC: account is zero"
      );
      await expect(opc.connect(attacker).unlockAchievement(alice.address, id)).to.be.reverted;
    });
  });

  // =====================================================================
  describe("courses", function () {
    beforeEach(async function () {
      await opc.connect(admin).registerBadge(1, "ipfs://course-badge", true);
      await opc.connect(admin).createCourse(1001, 500n, 1, true);
    });

    it("creates a course and reads config", async function () {
      expect(await opc.courseReward(1001)).to.equal(500n);
      expect(await opc.courseActive(1001)).to.equal(true);
      expect(await opc.totalCourses()).to.equal(1n);
    });

    it("rejects duplicate courses and unknown badges", async function () {
      await expect(opc.connect(admin).createCourse(1001, 1n, 0, true)).to.be.revertedWith(
        "OPC: course exists"
      );
      await expect(opc.connect(admin).createCourse(1002, 1n, 9, true)).to.be.revertedWith(
        "OPC: badge not registered"
      );
    });

    it("enroll requires an active course and is idempotent", async function () {
      await opc.connect(alice).enroll(1001);
      expect(await opc.enrolled(alice.address, 1001)).to.equal(true);
      await expect(opc.connect(alice).enroll(1001)).to.be.revertedWith("OPC: already enrolled");
      await opc.connect(admin).setCourse(1001, 500n, 1, false);
      await expect(opc.connect(bob).enroll(1001)).to.be.revertedWith("OPC: course inactive");
    });

    it("completeCourse pays OPC, grants XP and the badge, once only", async function () {
      await opc.connect(alice).enroll(1001);
      await expect(opc.connect(alice).completeCourse(1001))
        .to.emit(opc, "CourseCompleted")
        .withArgs(alice.address, 1001, 500n, 1);

      expect(await opc.balanceOf(alice.address, OPC)).to.equal(500n);
      expect(await opc.opcBalance(alice.address)).to.equal(500n);
      expect(await opc.xp(alice.address)).to.equal(500n);
      expect(await opc.hasBadge(alice.address, 1)).to.equal(true);
      expect(await opc.courseCompletionCount(1001)).to.equal(1n);

      await expect(opc.connect(alice).completeCourse(1001)).to.be.revertedWith(
        "OPC: already completed"
      );
    });

    it("cannot complete without enrolling", async function () {
      await expect(opc.connect(bob).completeCourse(1001)).to.be.revertedWith("OPC: not enrolled");
    });
  });

  // =====================================================================
  describe("rewards (idempotent)", function () {
    it("pays a reward once per idempotency key", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("quest"));
      await expect(opc.connect(rewarder).rewardUser(alice.address, 100n, reason, 42n))
        .to.emit(opc, "RewardPaid")
        .withArgs(alice.address, 100n, reason, 42n);
      expect(await opc.balanceOf(alice.address, OPC)).to.equal(100n);
      expect(await opc.rewardKeyUsed(42n)).to.equal(true);
      await expect(
        opc.connect(rewarder).rewardUser(alice.address, 100n, reason, 42n)
      ).to.be.revertedWith("OPC: reward key used");
    });

    it("rejects zero amount / zero address internally", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("q"));
      await expect(
        opc.connect(rewarder).rewardUser(alice.address, 0n, reason, 1n)
      ).to.be.revertedWith("OPC: amount=0");
      await expect(opc.connect(rewarder).rewardUser(ZERO, 1n, reason, 2n)).to.be.revertedWith(
        "OPC: to is zero"
      );
    });

    it("batch rewards many users atomically", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("batch"));
      await opc
        .connect(rewarder)
        .rewardUsers(
          [alice.address, bob.address, carol.address],
          [100n, 60n, 40n],
          [reason, reason, reason],
          [1n, 2n, 3n]
        );
      expect(await opc.balanceOf(alice.address, OPC)).to.equal(100n);
      expect(await opc.balanceOf(bob.address, OPC)).to.equal(60n);
      expect(await opc.balanceOf(carol.address, OPC)).to.equal(40n);
    });

    it("batch rejects length mismatch and duplicates", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("batch"));
      await expect(
        opc.connect(rewarder).rewardUsers([alice.address], [1n, 2n], [reason], [1n])
      ).to.be.revertedWith("OPC: length mismatch");
      await expect(
        opc
          .connect(rewarder)
          .rewardUsers([alice.address, bob.address], [1n, 1n], [reason, reason], [7n, 7n])
      ).to.be.revertedWith("OPC: reward key used");
    });

    it("batch rejects over the max batch size", async function () {
      const n = Number(MAX_BATCH) + 1;
      const recipients = Array(n).fill(alice.address);
      const amounts = Array(n).fill(1n);
      const reasons = Array(n).fill(ethers.ZeroHash);
      const keys = Array.from({ length: n }, (_, i) => BigInt(1000 + i));
      await expect(
        opc.connect(rewarder).rewardUsers(recipients, amounts, reasons, keys)
      ).to.be.revertedWith("OPC: batch too large");
    });

    it("non-rewarder cannot pay rewards", async function () {
      await expect(opc.connect(attacker).rewardUser(alice.address, 1n, ZERO_HASH, 1n)).to.be
        .reverted;
    });
  });

  // =====================================================================
  describe("treasury accounting", function () {
    beforeEach(async function () {
      await opc.connect(minter).mint(alice.address, OPC, 1000n, "0x");
    });

    it("records deposits and withdrawals", async function () {
      await opc.connect(alice).depositOPC(300n);
      expect(await opc.depositOf(alice.address)).to.equal(300n);
      expect(await opc.totalDeposits()).to.equal(300n);
      await opc.connect(alice).withdrawOPC(100n);
      expect(await opc.depositOf(alice.address)).to.equal(200n);
      expect(await opc.totalWithdrawals()).to.equal(100n);
    });

    it("rejects over-deposit and over-withdraw", async function () {
      await expect(opc.connect(alice).depositOPC(2000n)).to.be.revertedWith(
        "OPC: insufficient balance"
      );
      await expect(opc.connect(alice).withdrawOPC(1n)).to.be.revertedWith("OPC: exceeds deposit");
      await expect(opc.connect(alice).depositOPC(0n)).to.be.revertedWith("OPC: amount=0");
    });
  });

  // =====================================================================
  describe("burn & supply accounting", function () {
    it("holder can burn and totals update", async function () {
      await opc.connect(minter).mint(alice.address, OPC, 30n, "0x");
      await opc.connect(alice).burn(alice.address, OPC, 10n);
      expect(await opc.balanceOf(alice.address, OPC)).to.equal(20n);
      expect(await opc["totalSupply(uint256)"](OPC)).to.equal(20n);
      expect(await opc.totalBurned()).to.equal(10n);
    });

    it("cannot burn someone else's tokens without approval", async function () {
      await opc.connect(minter).mint(alice.address, OPC, 30n, "0x");
      await expect(opc.connect(attacker).burn(alice.address, OPC, 10n)).to.be.revertedWith(
        "OPC: not authorized to burn"
      );
    });
  });

  // =====================================================================
  describe("pause", function () {
    it("pauser can pause and unpause; minting is blocked while paused", async function () {
      await opc.connect(pauser).pause();
      await expect(opc.connect(minter).mint(treasury.address, OPC, 1n, "0x")).to.be.reverted;
      await opc.connect(pauser).unpause();
      await opc.connect(minter).mint(treasury.address, OPC, 1n, "0x");
      expect(await opc.balanceOf(treasury.address, OPC)).to.equal(1n);
    });

    it("non-pauser cannot pause", async function () {
      await expect(opc.connect(attacker).pause()).to.be.reverted;
    });
  });

  // =====================================================================
  describe("access control", function () {
    it("rejects mint from non-minter", async function () {
      await expect(opc.connect(attacker).mint(alice.address, OPC, 1n, "0x")).to.be.reverted;
    });

    it("supports ERC-1155 and AccessControl interfaces", async function () {
      expect(await opc.supportsInterface("0xd9b67a26")).to.equal(true); // ERC-1155
      expect(await opc.supportsInterface("0x7965db0b")).to.equal(true); // AccessControl
    });
  });

  // =====================================================================
  describe("upgradeability (UUPS)", function () {
    it("admin can upgrade and state is preserved", async function () {
      await opc.connect(rewarder).addXp(alice.address, 500n);
      await opc.connect(minter).mint(alice.address, OPC, 250n, "0x");

      const V2 = await ethers.getContractFactory("OryphemCoinV2Mock", admin);
      const upgraded = await upgrades.upgradeProxy(await opc.getAddress(), V2, {
        kind: "uups",
        call: { fn: "initializeV2", args: [admin.address, treasury.address] },
      });
      await upgraded.waitForDeployment();

      expect(await upgraded.xp(alice.address)).to.equal(500n);
      expect(await upgraded.level(alice.address)).to.equal(6n);
      expect(await upgraded.balanceOf(alice.address, OPC)).to.equal(250n);
      expect(await upgraded.v2Initialized()).to.equal(true);
      expect(await upgraded.version()).to.equal("v2");
    });

    it("non-admin cannot authorise an upgrade", async function () {
      const V2 = await ethers.getContractFactory("OryphemCoinV2Mock", attacker);
      await expect(
        upgrades.upgradeProxy(await opc.getAddress(), V2, { kind: "uups" })
      ).to.be.revertedWithCustomError(
        {
          interface: new ethers.Interface([
            "error AccessControlUnauthorizedAccount(address,bytes32)",
          ]),
        },
        "AccessControlUnauthorizedAccount"
      );
    });
  });

  // =====================================================================
  describe("invariants", function () {
    it("totalSupply never diverges from minted - burned for token 0", async function () {
      await opc.connect(minter).mint(alice.address, OPC, 100n, "0x");
      await opc.connect(minter).mint(bob.address, OPC, 50n, "0x");
      await opc.connect(alice).burn(alice.address, OPC, 30n);
      const supply = await opc["totalSupply(uint256)"](OPC);
      expect(supply).to.equal((await opc.totalMinted()) - (await opc.totalBurned()));
      expect(supply).to.equal(120n);
    });

    it("opcBalance mirror tracks transfers", async function () {
      await opc.connect(minter).mint(alice.address, OPC, 100n, "0x");
      expect(await opc.opcBalance(alice.address)).to.equal(100n);
      await opc.connect(alice).safeTransferFrom(alice.address, bob.address, OPC, 40n, "0x");
      expect(await opc.opcBalance(alice.address)).to.equal(60n);
      expect(await opc.opcBalance(bob.address)).to.equal(40n);
    });
  });

  // =====================================================================
  describe("fuzz — daily cap invariant", function () {
    it("never lets cumulative mint exceed the daily cap", async function () {
      await opc.connect(admin).setLimits(1000n, 5000n);
      for (let i = 0; i < 5; i++) {
        await opc.connect(minter).mint(treasury.address, OPC, 1000n, "0x");
      }
      await expect(opc.connect(minter).mint(treasury.address, OPC, 1n, "0x")).to.be.revertedWith(
        "OPC: exceeds daily cap"
      );
    });

    it("random XP amounts always yield the correct level", async function () {
      for (const v of [1n, 99n, 100n, 101n, 999n, 1000n, 12345n]) {
        await expect(opc.connect(rewarder).addXp(alice.address, v)).to.not.be.reverted;
      }
      const total = await opc.xp(alice.address);
      expect(await opc.level(alice.address)).to.equal(await opc.levelFromXp(total));
    });
  });
});
