const { expect } = require("chai");
const { ethers, upgrades } = require("hardhat");

// Asset token ids in the ERC-1155 multi-token contract.
const OPT = 0n; // OryphemToken — base currency, unlimited
const QTC = 1n; // QlootChain  — capped 1e15
const ORT = 2n; // OryphemIntelligence — AI credit (1 request = 1 ORT)

const BADGE_OFFSET = 1_000_000n;
const MAX_BATCH = 200n;
const LEVEL_STEP = 100n;
const MAX_QTC_SUPPLY = 1_000_000_000_000_000n; // 1e15
const UNLIMITED = (1n << 256n) - 1n;

const ZERO = ethers.ZeroAddress;
const ZERO_HASH = ethers.ZeroHash;

const role = (name) => ethers.keccak256(ethers.toUtf8Bytes(name));
const MINTER = role("MINTER_ROLE");
const REWARDER = role("REWARDER_ROLE");
const PAUSER = role("PAUSER_ROLE");
const URI_MANAGER = role("URI_MANAGER_ROLE");
const ROUTER = role("ROUTER_ROLE");
const ADMIN = role("ADMIN_ROLE");
const DEFAULT_ADMIN = ZERO_HASH;

/**
 * Deploys OryphemToken behind a UUPS proxy via hardhat-upgrades and wires up
 * the common roles used across the suite.
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

  const Factory = await ethers.getContractFactory("OryphemToken");
  const token = await upgrades.deployProxy(
    Factory,
    [
      "OryphemToken",
      "OPT",
      "https://metadata.qloot.example/opt/{id}.json",
      admin.address,
      treasury.address,
    ],
    { kind: "uups", initializer: "initialize" }
  );
  await token.waitForDeployment();

  await token.connect(admin).grantRole(MINTER, minter.address);
  await token.connect(admin).grantRole(REWARDER, rewarder.address);
  await token.connect(admin).grantRole(PAUSER, pauser.address);
  await token.connect(admin).grantRole(URI_MANAGER, uriManager.address);

  return {
    token,
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

describe("OryphemToken (OPT) — QLoot Academy ERC-1155 multi-token", function () {
  let token, admin, minter, rewarder, pauser, uriManager, alice, bob, carol, attacker, treasury;

  beforeEach(async function () {
    ({ token, admin, minter, rewarder, pauser, uriManager, alice, bob, carol, attacker, treasury } =
      await deployFixture());
  });

  // =====================================================================
  describe("initialization & metadata", function () {
    it("sets name, symbol, uri and treasury", async function () {
      expect(await token.name()).to.equal("OryphemToken");
      expect(await token.symbol()).to.equal("OPT");
      expect(await token.uri(OPT)).to.equal("https://metadata.qloot.example/opt/{id}.json");
      expect(await token.treasury()).to.equal(treasury.address);
    });

    it("exposes the three asset ids and proxy rates", async function () {
      expect(await token.OPT_TOKEN_ID()).to.equal(0n);
      expect(await token.QTC_TOKEN_ID()).to.equal(1n);
      expect(await token.ORT_TOKEN_ID()).to.equal(2n);
      const [optPerOrt, optPerQtc] = await token.proxyRates();
      expect(optPerOrt).to.equal(50n); // 1 ORT = 50 OPT
      expect(optPerQtc).to.equal(1000n); // 1 QTC = 1000 OPT
    });

    it("reports per-asset supply caps", async function () {
      expect(await token.maxSupplyOf(OPT)).to.equal(UNLIMITED); // OPT unlimited
      expect(await token.maxSupplyOf(QTC)).to.equal(MAX_QTC_SUPPLY); // QTC 1e15
      expect(await token.maxSupplyOf(ORT)).to.equal(UNLIMITED); // ORT unlimited
    });

    it("grants the full role set to the admin", async function () {
      for (const r of [DEFAULT_ADMIN, ADMIN, MINTER, REWARDER, PAUSER, URI_MANAGER, ROUTER]) {
        expect(await token.hasRole(r, admin.address)).to.equal(true);
      }
    });

    it("rejects re-initialization", async function () {
      await expect(
        token.initialize("x", "y", "z", admin.address, treasury.address)
      ).to.be.revertedWithCustomError(token, "InvalidInitialization");
    });

    it("only uri manager can set uri", async function () {
      await expect(token.connect(attacker).setURI("x")).to.be.reverted;
      await token.connect(uriManager).setURI("ipfs://new/");
      expect(await token.uri(0)).to.equal("ipfs://new/");
    });

    it("only admin can set treasury", async function () {
      await expect(token.connect(attacker).setTreasury(alice.address)).to.be.reverted;
      await token.connect(admin).setTreasury(alice.address);
      expect(await token.treasury()).to.equal(alice.address);
      await expect(token.connect(admin).setTreasury(ZERO)).to.be.revertedWithCustomError(
        token,
        "ZeroTreasury"
      );
    });
  });

  // =====================================================================
  describe("limits & minting", function () {
    it("mints OPT and tracks supply", async function () {
      await token.connect(minter).mint(treasury.address, OPT, 100n, "0x");
      expect(await token.balanceOf(treasury.address, OPT)).to.equal(100n);
      expect(await token["totalSupply(uint256)"](OPT)).to.equal(100n);
      expect(await token.totalMinted()).to.equal(100n);
    });

    it("OPT has no supply cap (can mint past any headline number)", async function () {
      const cap = await token.maxSupplyOf(OPT);
      expect(cap).to.equal(UNLIMITED);
      await token.connect(admin).setLimits(1n << 100n, 1n << 100n);
      await token.connect(minter).mint(treasury.address, OPT, 10n ** 21n, "0x");
      expect(await token["totalSupply(uint256)"](OPT)).to.equal(10n ** 21n);
    });

    it("caps the circulating QTC supply at 1e15", async function () {
      await token.connect(admin).setLimits(MAX_QTC_SUPPLY, MAX_QTC_SUPPLY);
      await token.connect(minter).mint(treasury.address, QTC, MAX_QTC_SUPPLY, "0x");
      expect(await token["totalSupply(uint256)"](QTC)).to.equal(MAX_QTC_SUPPLY);

      // New day so the daily cap resets — only the supply cap can fail now.
      await ethers.provider.send("evm_increaseTime", [24 * 60 * 60 + 1]);
      await ethers.provider.send("evm_mine", []);
      await expect(
        token.connect(minter).mint(treasury.address, QTC, 1n, "0x")
      ).to.be.revertedWithCustomError(token, "QtcSupplyExceeded");
    });

    it("burning QTC frees supply capacity again", async function () {
      await token.connect(admin).setLimits(MAX_QTC_SUPPLY, MAX_QTC_SUPPLY);
      await token.connect(minter).mint(admin.address, QTC, MAX_QTC_SUPPLY, "0x");
      await token.connect(admin).burn(admin.address, QTC, 1_000n);
      expect(await token["totalSupply(uint256)"](QTC)).to.equal(MAX_QTC_SUPPLY - 1_000n);

      await ethers.provider.send("evm_increaseTime", [24 * 60 * 60 + 1]);
      await ethers.provider.send("evm_mine", []);
      await token.connect(minter).mint(admin.address, QTC, 1_000n, "0x");
      expect(await token["totalSupply(uint256)"](QTC)).to.equal(MAX_QTC_SUPPLY);
    });

    it("does not cap badge ids", async function () {
      await token.connect(admin).registerBadge(7, "ipfs://badge/7", false);
      await token.connect(minter).mint(alice.address, BADGE_OFFSET + 7n, 1n, "0x");
      expect(await token.balanceOf(alice.address, BADGE_OFFSET + 7n)).to.equal(1n);
    });

    it("enforces maxMintPerTx", async function () {
      const max = await token.maxMintPerTx();
      await expect(
        token.connect(minter).mint(treasury.address, OPT, max + 1n, "0x")
      ).to.be.revertedWithCustomError(token, "ExceedsMaxMintPerTx");
    });

    it("enforces the rolling daily cap", async function () {
      await token.connect(admin).setLimits(1_000_000n, 1_500_000n);
      await token.connect(minter).mint(treasury.address, OPT, 1_000_000n, "0x");
      await expect(
        token.connect(minter).mint(treasury.address, OPT, 1_000_000n, "0x")
      ).to.be.revertedWithCustomError(token, "ExceedsDailyCap");
    });

    it("only admin can setLimits and cap >= max", async function () {
      await expect(token.connect(attacker).setLimits(1n, 2n)).to.be.reverted;
      await expect(token.connect(admin).setLimits(100n, 50n)).to.be.revertedWithCustomError(
        token,
        "CapBelowMax"
      );
    });

    it("mintBatch works and respects per-entry cap", async function () {
      await token.connect(minter).mintBatch(treasury.address, [OPT, QTC], [70n, 30n], "0x");
      expect(await token.balanceOf(treasury.address, OPT)).to.equal(70n);
      expect(await token.balanceOf(treasury.address, QTC)).to.equal(30n);
      const max = await token.maxMintPerTx();
      await expect(
        token.connect(minter).mintBatch(treasury.address, [OPT], [max + 1n], "0x")
      ).to.be.revertedWithCustomError(token, "ExceedsMaxMintPerTx");
    });
  });

  // =====================================================================
  describe("OryphemProxy (ORX) router", function () {
    beforeEach(async function () {
      // Fund alice with OPT to swap.
      await token.connect(minter).mint(alice.address, OPT, 100_000n, "0x");
    });

    it("swaps OPT -> ORT at 1 ORT = 50 OPT", async function () {
      // Buy 10 ORT (costs 500 OPT).
      await expect(token.connect(alice).swapOptFor(ORT, 10n))
        .to.emit(token, "Swapped")
        .withArgs(alice.address, alice.address, 500n, ORT, 10n);

      expect(await token.balanceOf(alice.address, ORT)).to.equal(10n);
      expect(await token.balanceOf(alice.address, OPT)).to.equal(99_500n);
      expect(await token.totalOrtMinted()).to.equal(10n);
      expect(await token.totalOptSwappedIn()).to.equal(500n);
    });

    it("swaps OPT -> QTC at 1 QTC = 1000 OPT", async function () {
      await token.connect(alice).swapOptFor(QTC, 2n);
      expect(await token.balanceOf(alice.address, QTC)).to.equal(2n);
      expect(await token.balanceOf(alice.address, OPT)).to.equal(98_000n);
      expect(await token.totalQtcMinted()).to.equal(2n);
    });

    it("rejects unsupported asset ids and zero amounts", async function () {
      await expect(token.connect(alice).swapOptFor(99n, 1n)).to.be.revertedWithCustomError(
        token,
        "UnsupportedAsset"
      );
      await expect(token.connect(alice).swapOptFor(ORT, 0n)).to.be.revertedWithCustomError(
        token,
        "ZeroAmount"
      );
    });

    it("reverts when the caller lacks enough OPT", async function () {
      // 100k OPT only buys 2000 ORT at 50 OPT each.
      await expect(token.connect(bob).swapOptFor(ORT, 1n)).to.be.reverted; // bob has 0 OPT
    });

    it("pays AI requests with ORT (1 request = 1 ORT)", async function () {
      await token.connect(alice).swapOptFor(ORT, 5n); // get 5 ORT
      await expect(token.connect(alice).payAiRequest(3n))
        .to.emit(token, "AiRequestPaid")
        .withArgs(alice.address, 3n, 3n);

      expect(await token.balanceOf(alice.address, ORT)).to.equal(2n);
      expect(await token.aiRequestsOf(alice.address)).to.equal(3n);
      expect(await token.totalAiRequests()).to.equal(3n);
    });

    it("rejects AI requests without enough ORT or zero requests", async function () {
      await expect(token.connect(alice).payAiRequest(0n)).to.be.revertedWithCustomError(
        token,
        "ZeroRequests"
      );
      await expect(token.connect(alice).payAiRequest(1n)).to.be.revertedWithCustomError(
        token,
        "InsufficientORT"
      );
    });

    it("only router role can mint assets through the router", async function () {
      await expect(token.connect(attacker).mint(alice.address, OPT, 1n, "0x")).to.be.reverted;
    });
  });

  // =====================================================================
  describe("XP & level", function () {
    it("computes level from XP", async function () {
      expect(await token.levelFromXp(0n)).to.equal(1n);
      expect(await token.levelFromXp(99n)).to.equal(1n);
      expect(await token.levelFromXp(100n)).to.equal(2n);
      expect(await token.levelFromXp(250n)).to.equal(3n);
    });

    it("adds XP and raises the level", async function () {
      await token.connect(rewarder).addXp(alice.address, 250n);
      expect(await token.xp(alice.address)).to.equal(250n);
      expect(await token.level(alice.address)).to.equal(3n);
      expect(await token.totalXpDistributed()).to.equal(250n);
    });

    it("only rewarder can add XP directly", async function () {
      await expect(token.connect(alice).addXp(alice.address, 10n)).to.be.revertedWithCustomError(
        token,
        "NotRewarder"
      );
    });

    it("admin can set a higher level but not lower", async function () {
      await token.connect(admin).setLevel(alice.address, 5n);
      expect(await token.level(alice.address)).to.equal(5n);
      await expect(token.connect(admin).setLevel(alice.address, 2n)).to.be.revertedWithCustomError(
        token,
        "LevelCannotDecrease"
      );
    });
  });

  // =====================================================================
  describe("badges", function () {
    beforeEach(async function () {
      await token.connect(admin).registerBadge(1, "ipfs://badge1", false);
      await token.connect(admin).registerBadge(2, "ipfs://badge2", true); // soulbound
    });

    it("registers badges and reads metadata", async function () {
      const b1 = await token.badges(1);
      expect(b1.uri).to.equal("ipfs://badge1");
      expect(b1.soulbound).to.equal(false);
      const b2 = await token.badges(2);
      expect(b2.soulbound).to.equal(true);
    });

    it("rejects badge id 0 and duplicates", async function () {
      await expect(token.connect(admin).registerBadge(0, "x", false)).to.be.revertedWithCustomError(
        token,
        "BadgeIdZero"
      );
      await expect(token.connect(admin).registerBadge(1, "x", false)).to.be.revertedWithCustomError(
        token,
        "BadgeExists"
      );
    });

    it("awards a badge once and mints a proof token", async function () {
      await token.connect(rewarder).awardBadge(alice.address, 1, "");
      expect(await token.hasBadge(alice.address, 1)).to.equal(true);
      expect(await token.userBadgeCount(alice.address)).to.equal(1n);
      expect(await token.badgeSupply(1)).to.equal(1n);
      const tokenId = BADGE_OFFSET + 1n;
      expect(await token.balanceOf(alice.address, tokenId)).to.equal(1n);

      // second award is a no-op
      await token.connect(rewarder).awardBadge(alice.address, 1, "");
      expect(await token.badgeSupply(1)).to.equal(1n);
      expect(await token.userBadgeCount(alice.address)).to.equal(1n);
    });

    it("cannot award an unregistered badge", async function () {
      await expect(
        token.connect(rewarder).awardBadge(alice.address, 9, "")
      ).to.be.revertedWithCustomError(token, "BadgeNotRegistered");
    });

    it("only admin can register, only rewarder can award", async function () {
      await expect(token.connect(attacker).registerBadge(3, "x", false)).to.be.reverted;
      await expect(token.connect(attacker).awardBadge(alice.address, 1, "")).to.be.reverted;
    });

    it("blocks transfer of soulbound badges but allows transferable ones", async function () {
      await token.connect(rewarder).awardBadge(alice.address, 1, ""); // transferable
      await token.connect(rewarder).awardBadge(alice.address, 2, ""); // soulbound
      await token
        .connect(alice)
        .safeTransferFrom(alice.address, bob.address, BADGE_OFFSET + 1n, 1n, "0x");
      await expect(
        token
          .connect(alice)
          .safeTransferFrom(alice.address, bob.address, BADGE_OFFSET + 2n, 1n, "0x")
      ).to.be.revertedWithCustomError(token, "BadgeSoulbound");
    });
  });

  // =====================================================================
  describe("achievements", function () {
    it("unlocks an achievement once", async function () {
      const id = ethers.keccak256(ethers.toUtf8Bytes("first_login"));
      await token.connect(rewarder).unlockAchievement(alice.address, id);
      expect(await token.achievementUnlocked(alice.address, id)).to.equal(true);
      expect(await token.achievementCount(alice.address)).to.equal(1n);
      await expect(
        token.connect(rewarder).unlockAchievement(alice.address, id)
      ).to.be.revertedWithCustomError(token, "AchievementAlreadyUnlocked");
    });

    it("rejects zero id / zero account and non-rewarder", async function () {
      const id = ethers.keccak256(ethers.toUtf8Bytes("x"));
      await expect(
        token.connect(rewarder).unlockAchievement(alice.address, ZERO_HASH)
      ).to.be.revertedWithCustomError(token, "AchievementIdZero");
      await expect(
        token.connect(rewarder).unlockAchievement(ZERO, id)
      ).to.be.revertedWithCustomError(token, "ZeroAccount");
      await expect(token.connect(attacker).unlockAchievement(alice.address, id)).to.be.reverted;
    });
  });

  // =====================================================================
  describe("courses", function () {
    beforeEach(async function () {
      await token.connect(admin).registerBadge(1, "ipfs://course-badge", true);
      await token.connect(admin).createCourse(1001, 500n, 1, true);
    });

    it("creates a course and reads config", async function () {
      const c = await token.courses(1001);
      expect(c.rewardAmount).to.equal(500n);
      expect(c.active).to.equal(true);
      expect(await token.totalCourses()).to.equal(1n);
    });

    it("rejects duplicate courses and unknown badges", async function () {
      await expect(
        token.connect(admin).createCourse(1001, 1n, 0, true)
      ).to.be.revertedWithCustomError(token, "CourseExists");
      await expect(
        token.connect(admin).createCourse(1002, 1n, 9, true)
      ).to.be.revertedWithCustomError(token, "BadgeNotRegistered");
    });

    it("enroll requires an active course and is idempotent", async function () {
      await token.connect(alice).enroll(1001);
      expect(await token.enrolled(alice.address, 1001)).to.equal(true);
      await expect(token.connect(alice).enroll(1001)).to.be.revertedWithCustomError(
        token,
        "AlreadyEnrolled"
      );
      await token.connect(admin).setCourse(1001, 500n, 1, false);
      await expect(token.connect(bob).enroll(1001)).to.be.revertedWithCustomError(
        token,
        "CourseInactive"
      );
    });

    it("completeCourse pays OPT, grants XP and the badge, once only", async function () {
      await token.connect(alice).enroll(1001);
      await expect(token.connect(alice).completeCourse(1001))
        .to.emit(token, "CourseCompleted")
        .withArgs(alice.address, 1001, 500n, 1);

      expect(await token.balanceOf(alice.address, OPT)).to.equal(500n);
      expect(await token.opcBalance(alice.address)).to.equal(500n);
      expect(await token.xp(alice.address)).to.equal(500n);
      expect(await token.hasBadge(alice.address, 1)).to.equal(true);
      expect(await token.courseCompletionCount(1001)).to.equal(1n);

      await expect(token.connect(alice).completeCourse(1001)).to.be.revertedWithCustomError(
        token,
        "AlreadyCompleted"
      );
    });

    it("cannot complete without enrolling", async function () {
      await expect(token.connect(bob).completeCourse(1001)).to.be.revertedWithCustomError(
        token,
        "NotEnrolled"
      );
    });
  });

  // =====================================================================
  describe("rewards (idempotent)", function () {
    it("pays a reward once per idempotency key", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("quest"));
      await expect(token.connect(rewarder).rewardUser(alice.address, 100n, reason, 42n))
        .to.emit(token, "RewardPaid")
        .withArgs(alice.address, 100n, reason, 42n);
      expect(await token.balanceOf(alice.address, OPT)).to.equal(100n);
      expect(await token.rewardKeyUsed(42n)).to.equal(true);
      await expect(
        token.connect(rewarder).rewardUser(alice.address, 100n, reason, 42n)
      ).to.be.revertedWithCustomError(token, "RewardKeyUsed");
    });

    it("rejects zero amount / zero address internally", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("q"));
      await expect(
        token.connect(rewarder).rewardUser(alice.address, 0n, reason, 1n)
      ).to.be.revertedWithCustomError(token, "ZeroAmount");
      await expect(
        token.connect(rewarder).rewardUser(ZERO, 1n, reason, 2n)
      ).to.be.revertedWithCustomError(token, "ZeroRecipient");
    });

    it("batch rewards many users atomically", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("batch"));
      await token
        .connect(rewarder)
        .rewardUsers(
          [alice.address, bob.address, carol.address],
          [100n, 60n, 40n],
          [reason, reason, reason],
          [1n, 2n, 3n]
        );
      expect(await token.balanceOf(alice.address, OPT)).to.equal(100n);
      expect(await token.balanceOf(bob.address, OPT)).to.equal(60n);
      expect(await token.balanceOf(carol.address, OPT)).to.equal(40n);
    });

    it("batch rejects length mismatch and duplicates", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("batch"));
      await expect(
        token.connect(rewarder).rewardUsers([alice.address], [1n, 2n], [reason], [1n])
      ).to.be.revertedWithCustomError(token, "LengthMismatch");
      await expect(
        token
          .connect(rewarder)
          .rewardUsers([alice.address, bob.address], [1n, 1n], [reason, reason], [7n, 7n])
      ).to.be.revertedWithCustomError(token, "RewardKeyUsed");
    });

    it("batch rejects over the max batch size", async function () {
      const n = Number(MAX_BATCH) + 1;
      const recipients = Array(n).fill(alice.address);
      const amounts = Array(n).fill(1n);
      const reasons = Array(n).fill(ethers.ZeroHash);
      const keys = Array.from({ length: n }, (_, i) => BigInt(1000 + i));
      await expect(
        token.connect(rewarder).rewardUsers(recipients, amounts, reasons, keys)
      ).to.be.revertedWithCustomError(token, "BatchTooLarge");
    });

    it("non-rewarder cannot pay rewards", async function () {
      await expect(token.connect(attacker).rewardUser(alice.address, 1n, ZERO_HASH, 1n)).to.be
        .reverted;
    });
  });

  // =====================================================================
  describe("treasury accounting", function () {
    beforeEach(async function () {
      await token.connect(minter).mint(alice.address, OPT, 1000n, "0x");
    });

    it("records deposits and withdrawals", async function () {
      await token.connect(alice).depositOPC(300n);
      expect(await token.depositOf(alice.address)).to.equal(300n);
      expect(await token.totalDeposits()).to.equal(300n);
      await token.connect(alice).withdrawOPC(100n);
      expect(await token.depositOf(alice.address)).to.equal(200n);
      expect(await token.totalWithdrawals()).to.equal(100n);
    });

    it("rejects over-deposit and over-withdraw", async function () {
      await expect(token.connect(alice).depositOPC(2000n)).to.be.revertedWithCustomError(
        token,
        "InsufficientBalance"
      );
      await expect(token.connect(alice).withdrawOPC(1n)).to.be.revertedWithCustomError(
        token,
        "ExceedsDeposit"
      );
      await expect(token.connect(alice).depositOPC(0n)).to.be.revertedWithCustomError(
        token,
        "ZeroAmount"
      );
    });
  });

  // =====================================================================
  describe("burn & supply accounting", function () {
    it("holder can burn and totals update", async function () {
      await token.connect(minter).mint(alice.address, OPT, 30n, "0x");
      await token.connect(alice).burn(alice.address, OPT, 10n);
      expect(await token.balanceOf(alice.address, OPT)).to.equal(20n);
      expect(await token["totalSupply(uint256)"](OPT)).to.equal(20n);
      expect(await token.totalBurned()).to.equal(10n);
    });

    it("cannot burn someone else's tokens without approval", async function () {
      await token.connect(minter).mint(alice.address, OPT, 30n, "0x");
      await expect(
        token.connect(attacker).burn(alice.address, OPT, 10n)
      ).to.be.revertedWithCustomError(token, "NotAuthorizedToBurn");
    });
  });

  // =====================================================================
  describe("pause", function () {
    it("pauser can pause and unpause; minting is blocked while paused", async function () {
      await token.connect(pauser).pause();
      await expect(token.connect(minter).mint(treasury.address, OPT, 1n, "0x")).to.be.reverted;
      await token.connect(pauser).unpause();
      await token.connect(minter).mint(treasury.address, OPT, 1n, "0x");
      expect(await token.balanceOf(treasury.address, OPT)).to.equal(1n);
    });

    it("non-pauser cannot pause", async function () {
      await expect(token.connect(attacker).pause()).to.be.reverted;
    });
  });

  // =====================================================================
  describe("access control", function () {
    it("rejects mint from non-minter", async function () {
      await expect(token.connect(attacker).mint(alice.address, OPT, 1n, "0x")).to.be.reverted;
    });

    it("supports ERC-1155 and AccessControl interfaces", async function () {
      expect(await token.supportsInterface("0xd9b67a26")).to.equal(true); // ERC-1155
      expect(await token.supportsInterface("0x7965db0b")).to.equal(true); // AccessControl
    });
  });

  // =====================================================================
  describe("upgradeability (UUPS)", function () {
    it("admin can upgrade and state is preserved", async function () {
      await token.connect(rewarder).addXp(alice.address, 500n);
      await token.connect(minter).mint(alice.address, OPT, 250n, "0x");

      const V2 = await ethers.getContractFactory("OryphemTokenV2Mock", admin);
      const upgraded = await upgrades.upgradeProxy(await token.getAddress(), V2, {
        kind: "uups",
        call: { fn: "initializeV2", args: [admin.address, treasury.address] },
      });
      await upgraded.waitForDeployment();

      expect(await upgraded.xp(alice.address)).to.equal(500n);
      expect(await upgraded.level(alice.address)).to.equal(6n);
      expect(await upgraded.balanceOf(alice.address, OPT)).to.equal(250n);
      expect(await upgraded.v2Initialized()).to.equal(true);
      expect(await upgraded.version()).to.equal("v2");
    });

    it("non-admin cannot authorise an upgrade", async function () {
      const V2 = await ethers.getContractFactory("OryphemTokenV2Mock", attacker);
      await expect(
        upgrades.upgradeProxy(await token.getAddress(), V2, { kind: "uups" })
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
    it("totalSupply never diverges from minted - burned for OPT (id 0)", async function () {
      await token.connect(minter).mint(alice.address, OPT, 100n, "0x");
      await token.connect(minter).mint(bob.address, OPT, 50n, "0x");
      await token.connect(alice).burn(alice.address, OPT, 30n);
      const supply = await token["totalSupply(uint256)"](OPT);
      expect(supply).to.equal((await token.totalMinted()) - (await token.totalBurned()));
      expect(supply).to.equal(120n);
    });

    it("opcBalance mirror tracks transfers", async function () {
      await token.connect(minter).mint(alice.address, OPT, 100n, "0x");
      expect(await token.opcBalance(alice.address)).to.equal(100n);
      await token.connect(alice).safeTransferFrom(alice.address, bob.address, OPT, 40n, "0x");
      expect(await token.opcBalance(alice.address)).to.equal(60n);
      expect(await token.opcBalance(bob.address)).to.equal(40n);
    });
  });

  // =====================================================================
  describe("fuzz — daily cap invariant", function () {
    it("never lets cumulative mint exceed the daily cap", async function () {
      await token.connect(admin).setLimits(1000n, 5000n);
      for (let i = 0; i < 5; i++) {
        await token.connect(minter).mint(treasury.address, OPT, 1000n, "0x");
      }
      await expect(
        token.connect(minter).mint(treasury.address, OPT, 1n, "0x")
      ).to.be.revertedWithCustomError(token, "ExceedsDailyCap");
    });

    it("random XP amounts always yield the correct level", async function () {
      for (const v of [1n, 99n, 100n, 101n, 999n, 1000n, 12345n]) {
        await expect(token.connect(rewarder).addXp(alice.address, v)).to.not.be.reverted;
      }
      const total = await token.xp(alice.address);
      expect(await token.level(alice.address)).to.equal(await token.levelFromXp(total));
    });
  });
});
