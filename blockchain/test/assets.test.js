const { expect } = require("chai");
const { ethers, upgrades } = require("hardhat");

// QLoot digital assets — 4 separate UUPS-proxy contracts, each with its own
// address: OPT (OryphemToken), QTC (QlootChain), ORT (OryphemIntelligence) and
// the ORX router (OryphemProxy).
const ASSET_ID = 0n; // each asset uses token id 0 within its own contract
const QTC_MAX_SUPPLY = 1_000_000_000_000_000n; // 1e15

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

const URI = "https://metadata.qloot.example/{id}.json";

/** Deploy OPT, QTC, ORT and the ORX router (all behind UUPS proxies). */
async function deployAll() {
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

  const Opt = await ethers.getContractFactory("OryphemToken");
  const opt = await upgrades.deployProxy(Opt, ["OryphemToken", "OPT", URI, admin.address], {
    kind: "uups",
    initializer: "initialize",
  });
  await opt.waitForDeployment();

  const Qtc = await ethers.getContractFactory("QlootChain");
  const qtc = await upgrades.deployProxy(Qtc, ["QlootChain", "QTC", URI, admin.address], {
    kind: "uups",
    initializer: "initialize",
  });
  await qtc.waitForDeployment();

  const Ort = await ethers.getContractFactory("OryphemIntelligence");
  const ort = await upgrades.deployProxy(Ort, ["OryphemIntelligence", "ORT", URI, admin.address], {
    kind: "uups",
    initializer: "initialize",
  });
  await ort.waitForDeployment();

  const Proxy = await ethers.getContractFactory("OryphemProxy");
  const orx = await upgrades.deployProxy(
    Proxy,
    [
      admin.address,
      await opt.getAddress(),
      await qtc.getAddress(),
      await ort.getAddress(),
      treasury.address,
    ],
    { kind: "uups", initializer: "initialize" }
  );
  await orx.waitForDeployment();

  await opt.connect(admin).grantRole(MINTER, minter.address);
  await opt.connect(admin).grantRole(REWARDER, rewarder.address);
  await opt.connect(admin).grantRole(PAUSER, pauser.address);
  await opt.connect(admin).grantRole(URI_MANAGER, uriManager.address);

  // Grant the ORX router ROUTER_ROLE on each asset so it can settle swaps.
  for (const asset of [opt, qtc, ort]) {
    await asset.connect(admin).grantRole(ROUTER, await orx.getAddress());
  }

  return {
    opt,
    qtc,
    ort,
    orx,
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

describe("QLoot digital assets — OPT / QTC / ORT + ORX router", function () {
  let opt, qtc, ort, orx;
  let admin, minter, rewarder, pauser, uriManager, alice, bob, carol, attacker, treasury;

  beforeEach(async function () {
    ({
      opt,
      qtc,
      ort,
      orx,
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
    } = await deployAll());
  });

  // =====================================================================
  describe("deployment & metadata", function () {
    it("deploys 4 distinct contracts with distinct addresses", async function () {
      const addrs = await Promise.all([
        opt.getAddress(),
        qtc.getAddress(),
        ort.getAddress(),
        orx.getAddress(),
      ]);
      expect(new Set(addrs.map((a) => a.toLowerCase())).size).to.equal(4);
    });

    it("each asset reports its name, symbol and id 0", async function () {
      expect(await opt.name()).to.equal("OryphemToken");
      expect(await opt.symbol()).to.equal("OPT");
      expect(await opt.ASSET_ID()).to.equal(0n);

      expect(await qtc.name()).to.equal("QlootChain");
      expect(await qtc.symbol()).to.equal("QTC");

      expect(await ort.name()).to.equal("OryphemIntelligence");
      expect(await ort.symbol()).to.equal("ORT");
    });

    it("supports the ERC-1155 interface", async function () {
      for (const a of [opt, qtc, ort]) {
        expect(await a.supportsInterface("0xd9b67a26")).to.equal(true); // ERC-1155
      }
    });

    it("grants the admin every role on a fresh asset", async function () {
      for (const r of [DEFAULT_ADMIN, ADMIN, MINTER, REWARDER, PAUSER, URI_MANAGER, ROUTER]) {
        expect(await opt.hasRole(r, admin.address)).to.equal(true);
      }
    });

    it("rejects re-initialization", async function () {
      await expect(opt.initialize("x", "y", "z", admin.address)).to.be.revertedWithCustomError(
        opt,
        "InvalidInitialization"
      );
    });
  });

  // =====================================================================
  describe("OPT — unlimited base currency", function () {
    it("mints OPT and tracks supply", async function () {
      await opt.connect(minter).mint(treasury.address, 100n);
      expect(await opt.balanceOf(treasury.address, ASSET_ID)).to.equal(100n);
      expect(await opt["totalSupply(uint256)"](ASSET_ID)).to.equal(100n);
      expect(await opt.totalMinted()).to.equal(100n);
    });

    it("has no supply cap (maxSupply = 0) and can mint a huge amount", async function () {
      expect(await opt.maxSupply()).to.equal(0n);
      await opt.connect(admin).setLimits(1n << 100n, 1n << 100n);
      await opt.connect(minter).mint(treasury.address, 10n ** 21n);
      expect(await opt["totalSupply(uint256)"](ASSET_ID)).to.equal(10n ** 21n);
    });

    it("burn reduces supply", async function () {
      await opt.connect(minter).mint(alice.address, 30n);
      await opt.connect(alice).burn(alice.address, 10n);
      expect(await opt.balanceOf(alice.address, ASSET_ID)).to.equal(20n);
      expect(await opt.totalBurned()).to.equal(10n);
    });

    it("enforces per-tx and daily caps", async function () {
      await opt.connect(admin).setLimits(1000n, 5000n);
      await expect(opt.connect(minter).mint(treasury.address, 1001n)).to.be.revertedWithCustomError(
        opt,
        "ExceedsMaxMintPerTx"
      );
      for (let i = 0; i < 5; i++) await opt.connect(minter).mint(treasury.address, 1000n);
      await expect(opt.connect(minter).mint(treasury.address, 1n)).to.be.revertedWithCustomError(
        opt,
        "ExceedsDailyCap"
      );
    });

    it("only admin can setLimits; cap must be >= max", async function () {
      await expect(opt.connect(attacker).setLimits(1n, 2n)).to.be.reverted;
      await expect(opt.connect(admin).setLimits(100n, 50n)).to.be.revertedWithCustomError(
        opt,
        "CapBelowMax"
      );
    });

    it("rejects mint from a non-minter", async function () {
      await expect(opt.connect(attacker).mint(alice.address, 1n)).to.be.reverted;
    });
  });

  // =====================================================================
  describe("QTC — premium asset capped at 1e15", function () {
    it("exposes the 1e15 cap", async function () {
      expect(await qtc.maxSupply()).to.equal(QTC_MAX_SUPPLY);
    });

    it("caps the circulating supply", async function () {
      await qtc.connect(admin).setLimits(QTC_MAX_SUPPLY, QTC_MAX_SUPPLY);
      await qtc.connect(admin).mint(treasury.address, QTC_MAX_SUPPLY);
      expect(await qtc["totalSupply(uint256)"](ASSET_ID)).to.equal(QTC_MAX_SUPPLY);

      await ethers.provider.send("evm_increaseTime", [24 * 60 * 60 + 1]);
      await ethers.provider.send("evm_mine", []);
      await expect(qtc.connect(admin).mint(treasury.address, 1n)).to.be.revertedWithCustomError(
        qtc,
        "SupplyExceeded"
      );
    });

    it("burn frees capacity again", async function () {
      await qtc.connect(admin).setLimits(QTC_MAX_SUPPLY, QTC_MAX_SUPPLY);
      await qtc.connect(admin).mint(admin.address, QTC_MAX_SUPPLY);
      await qtc.connect(admin).burn(admin.address, 1_000n);
      expect(await qtc["totalSupply(uint256)"](ASSET_ID)).to.equal(QTC_MAX_SUPPLY - 1_000n);

      await ethers.provider.send("evm_increaseTime", [24 * 60 * 60 + 1]);
      await ethers.provider.send("evm_mine", []);
      await qtc.connect(admin).mint(admin.address, 1_000n);
      expect(await qtc["totalSupply(uint256)"](ASSET_ID)).to.equal(QTC_MAX_SUPPLY);
    });

    it("admin can raise the cap but not below current supply", async function () {
      await qtc.connect(admin).mint(alice.address, 500n);
      await expect(qtc.connect(admin).setMaxSupply(100n)).to.be.revertedWithCustomError(
        qtc,
        "CapBelowMax"
      );
      await qtc.connect(admin).setMaxSupply(1_000_000n);
      expect(await qtc.maxSupply()).to.equal(1_000_000n);
    });
  });

  // =====================================================================
  describe("ORT — AI credit", function () {
    it("mints ORT (no cap) and tracks supply", async function () {
      expect(await ort.maxSupply()).to.equal(0n);
      await ort.connect(admin).mint(alice.address, 42n);
      expect(await ort.balanceOf(alice.address, ASSET_ID)).to.equal(42n);
    });
  });

  // =====================================================================
  describe("ORX (OryphemProxy) router", function () {
    it("exposes the fixed rates: 1 ORT = 50 OPT, 1 QTC = 1000 OPT", async function () {
      const [optPerOrt, optPerQtc] = await orx.proxyRates();
      expect(optPerOrt).to.equal(50n);
      expect(optPerQtc).to.equal(1000n);
      expect(await orx.ORT_RATE()).to.equal(50n);
      expect(await orx.QTC_RATE()).to.equal(1000n);
    });

    it("updates the rates via setRates (ADMIN_ROLE) and uses them on swap", async function () {
      // Non-admin cannot change rates.
      await expect(orx.connect(alice).setRates(25n, 500n)).to.be.revertedWithCustomError(
        orx,
        "AccessControlUnauthorizedAccount"
      );

      await expect(orx.connect(admin).setRates(25n, 500n))
        .to.emit(orx, "RatesUpdated")
        .withArgs(25n, 500n);

      const [optPerOrt, optPerQtc] = await orx.proxyRates();
      expect(optPerOrt).to.equal(25n);
      expect(optPerQtc).to.equal(500n);

      // A swap now charges the governed rate (25 OPT per ORT).
      await opt.connect(minter).mint(alice.address, 1_000n);
      await orx.connect(alice).swapOptFor(2n, 4n); // 4 ORT * 25 = 100 OPT
      expect(await opt.balanceOf(alice.address, ASSET_ID)).to.equal(900n);
      expect(await ort.balanceOf(alice.address, ASSET_ID)).to.equal(4n);
    });

    it("setRates(0,0) falls back to the default rates", async function () {
      await orx.connect(admin).setRates(0n, 0n);
      const [optPerOrt, optPerQtc] = await orx.proxyRates();
      expect(optPerOrt).to.equal(50n);
      expect(optPerQtc).to.equal(1000n);
    });

    it("stores the OPT/QTC/ORT addresses and treasury", async function () {
      expect(await orx.opt()).to.equal(await opt.getAddress());
      expect(await orx.qtc()).to.equal(await qtc.getAddress());
      expect(await orx.ort()).to.equal(await ort.getAddress());
      expect(await orx.treasury()).to.equal(treasury.address);
    });

    it("swaps OPT -> ORT at 50 OPT per ORT", async function () {
      await opt.connect(minter).mint(alice.address, 100_000n);
      await expect(orx.connect(alice).swapOptFor(2n, 10n))
        .to.emit(orx, "Routed")
        .withArgs(alice.address, 2n, 500n, 10n);

      expect(await ort.balanceOf(alice.address, ASSET_ID)).to.equal(10n);
      expect(await opt.balanceOf(alice.address, ASSET_ID)).to.equal(99_500n);
      expect(await orx.totalOrtMinted()).to.equal(10n);
      expect(await orx.totalOptSwappedIn()).to.equal(500n);
    });

    it("swaps OPT -> QTC at 1000 OPT per QTC", async function () {
      await opt.connect(minter).mint(alice.address, 100_000n);
      await orx.connect(alice).swapOptFor(1n, 2n);
      expect(await qtc.balanceOf(alice.address, ASSET_ID)).to.equal(2n);
      expect(await opt.balanceOf(alice.address, ASSET_ID)).to.equal(98_000n);
      expect(await orx.totalQtcMinted()).to.equal(2n);
    });

    it("rejects unsupported asset ids and zero amounts", async function () {
      await expect(orx.connect(alice).swapOptFor(99n, 1n)).to.be.revertedWithCustomError(
        orx,
        "UnsupportedAsset"
      );
      await expect(orx.connect(alice).swapOptFor(2n, 0n)).to.be.revertedWithCustomError(
        orx,
        "ZeroAmount"
      );
    });

    it("reverts a swap when the caller lacks OPT", async function () {
      await expect(orx.connect(bob).swapOptFor(2n, 1n)).to.be.revertedWithCustomError(
        orx,
        "InsufficientBalance"
      );
    });

    it("pays AI requests with ORT (1 request = 1 ORT)", async function () {
      await opt.connect(minter).mint(alice.address, 1000n);
      await orx.connect(alice).swapOptFor(2n, 5n); // 5 ORT
      await expect(orx.connect(alice).payAiRequest(3n))
        .to.emit(orx, "AiRequestPaid")
        .withArgs(alice.address, 3n, 3n);
      expect(await ort.balanceOf(alice.address, ASSET_ID)).to.equal(2n);
      expect(await orx.totalAiRequests()).to.equal(3n);
    });

    it("rejects AI requests without enough ORT / zero requests", async function () {
      await expect(orx.connect(alice).payAiRequest(0n)).to.be.revertedWithCustomError(
        orx,
        "ZeroAmount"
      );
      await expect(orx.connect(alice).payAiRequest(1n)).to.be.revertedWithCustomError(
        orx,
        "InsufficientBalance"
      );
    });

    it("only admin can update assets/treasury", async function () {
      await expect(orx.connect(attacker).setAssets(alice.address, bob.address, carol.address)).to.be
        .reverted;
      await orx.connect(admin).setTreasury(alice.address);
      expect(await orx.treasury()).to.equal(alice.address);
    });

    it("router-only asset burn/mint are gated to ROUTER_ROLE", async function () {
      await opt.connect(minter).mint(alice.address, 100n);
      await expect(opt.connect(attacker).routerBurn(alice.address, 1n)).to.be.reverted;
      await expect(opt.connect(attacker).routerMint(alice.address, 1n)).to.be.reverted;
    });
  });

  // =====================================================================
  describe("rewards", function () {
    it("pays an idempotent reward once per key", async function () {
      const reason = ethers.keccak256(ethers.toUtf8Bytes("quest"));
      await opt.connect(rewarder).rewardUser(alice.address, 100n, reason, 7n);
      expect(await opt.balanceOf(alice.address, ASSET_ID)).to.equal(100n);
      await expect(
        opt.connect(rewarder).rewardUser(alice.address, 100n, reason, 7n)
      ).to.be.revertedWithCustomError(opt, "RewardKeyUsed");
    });

    it("non-rewarder cannot pay rewards", async function () {
      await expect(opt.connect(attacker).rewardUser(alice.address, 1n, ZERO_HASH, 1n)).to.be
        .reverted;
    });
  });

  // =====================================================================
  describe("pause & access control", function () {
    it("pauser can pause; minting is blocked while paused", async function () {
      await opt.connect(pauser).pause();
      await expect(opt.connect(minter).mint(treasury.address, 1n)).to.be.reverted;
      await opt.connect(pauser).unpause();
      await opt.connect(minter).mint(treasury.address, 1n);
      expect(await opt.balanceOf(treasury.address, ASSET_ID)).to.equal(1n);
    });

    it("only uri manager can set uri", async function () {
      await expect(opt.connect(attacker).setURI("x")).to.be.reverted;
      await opt.connect(uriManager).setURI("ipfs://new/");
      expect(await opt.uri(ASSET_ID)).to.equal("ipfs://new/");
    });
  });

  // =====================================================================
  describe("upgradeability (UUPS)", function () {
    it("admin can upgrade OPT and state is preserved", async function () {
      await opt.connect(minter).mint(alice.address, 250n);
      const V2 = await ethers.getContractFactory("OryphemTokenV2Mock", admin);
      const upgraded = await upgrades.upgradeProxy(await opt.getAddress(), V2, { kind: "uups" });
      await upgraded.waitForDeployment();
      expect(await upgraded.balanceOf(alice.address, ASSET_ID)).to.equal(250n);
      expect(await upgraded.version()).to.equal("v2");
    });

    it("non-admin cannot authorise an upgrade", async function () {
      const V2 = await ethers.getContractFactory("OryphemTokenV2Mock", attacker);
      await expect(
        upgrades.upgradeProxy(await opt.getAddress(), V2, { kind: "uups" })
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
  describe("document anchoring (certificates)", function () {
    const anchorKey = ethers.keccak256(ethers.toUtf8Bytes("cert:QTC-1"));
    const docHash = ethers.keccak256(ethers.toUtf8Bytes("certificate-payload"));

    it("anchors a hash and emits DocumentAnchored (router only)", async function () {
      // The ORX router holds ROUTER_ROLE on QTC; route the call through it.
      await expect(orx.connect(admin).anchorOnQtc(anchorKey, docHash))
        .to.emit(qtc, "DocumentAnchored")
        .withArgs(anchorKey, docHash, await orx.getAddress());
      expect(await qtc.documentAnchorOf(anchorKey)).to.equal(docHash);
    });

    it("rejects a direct anchor from a non-router account", async function () {
      await expect(
        qtc.connect(attacker).anchorDocument(anchorKey, docHash)
      ).to.be.revertedWithCustomError(qtc, "AccessControlUnauthorizedAccount");
    });

    it("is idempotent per key (no double-anchor)", async function () {
      await orx.connect(admin).anchorOnQtc(anchorKey, docHash);
      await expect(
        orx.connect(admin).anchorOnQtc(anchorKey, docHash)
      ).to.be.revertedWithCustomError(qtc, "AnchorKeyUsed");
    });
  });
});
