<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type {
    Wallet,
    WalletAssets,
    LedgerEntry,
    Reward,
    BlockchainStatus,
    BlockchainTx,
  } from "$lib/types";
  import {
    formatDate,
    formatNumber,
    relativeTime,
    shortHash,
    etherscanUrl,
    statusLabel,
  } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import { opt } from "$lib/stores/opt";
  import { connectWalletAddress, hasInjectedWallet } from "$lib/utils/metamask";

  const PAGE = 10;
  let wallet: Wallet | null = null;
  let assets: WalletAssets | null = null;
  let ledger: LedgerEntry[] = [];
  let rewards: Reward[] = [];
  let status: BlockchainStatus | null = null;
  let txs: BlockchainTx[] = [];
  let loading = true;
  let error = "";
  let withdrawAmount = 0;
  let withdrawAddr = "";
  let withdrawMsg = "";
  // Ledger integrity check (GET /wallet/reconciliation).
  let recon: { ok: boolean; cached_balance: number; computed_balance: number } | null = null;
  let reconLoading = false;

  async function checkReconciliation() {
    reconLoading = true;
    error = "";
    try {
      recon = await api.get<{
        ok: boolean;
        cached_balance: number;
        computed_balance: number;
      }>("/wallet/reconciliation");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memeriksa saldo";
    } finally {
      reconLoading = false;
    }
  }

  // ORX swap (OPT -> QTC/ORT) state.
  const ORX_RATES: Record<string, number> = { ORT: 50, QTC: 1000 };
  let swapAsset = "ORT";
  let swapAmount = 0;
  let swapBusy = false;
  let swapMsg = "";
  // AI request (ORT spend) state.
  let aiRequests = 1;
  let aiBusy = false;
  let aiMsg = "";

  // Personal wallet ("wallet saya") editing.
  let walletAddrDraft = "";
  let walletSaving = false;
  let walletMsg = "";
  let metamaskAvailable = false;

  // Independent pagers for the three lists.
  let ledgerPage = 1;
  let ledgerHasMore = false;
  let ledgerLoading = false;
  let rewardsPage = 1;
  let rewardsHasMore = false;
  let rewardsLoading = false;
  let txPage = 1;
  let txHasMore = false;
  let txLoading = false;

  // Internal transfer state.
  let recipients: { user_id: string; full_name: string; email_masked: string; handle: string }[] =
    [];
  let recipientQuery = "";
  let recipientBusy = false;
  let transferTarget: {
    user_id: string;
    full_name: string;
    email_masked: string;
    handle: string;
  } | null = null;
  let transferAmount = 0;
  let transferNote = "";
  let transferMsg = "";
  let transferBusy = false;
  let withdrawBusy = false;

  let copiedAddr = false;
  let copyError = "";
  async function copyToClipboard(text: string) {
    if (!text) return;
    copyError = "";
    try {
      await navigator.clipboard.writeText(text);
      copiedAddr = true;
      setTimeout(() => (copiedAddr = false), 2000);
    } catch {
      // Clipboard can be blocked (insecure context, permissions). Tell the user
      // instead of failing silently so they don't think the address was copied.
      copyError = "Tidak dapat menyalin otomatis. Salin manual dari alamat di atas.";
    }
  }

  function setWithdrawPercent(pct: number) {
    if (!wallet) return;
    withdrawAmount = Math.max(0, Math.floor((wallet.available * pct) / 100));
  }

  function setTransferPercent(pct: number) {
    if (!wallet) return;
    transferAmount = Math.max(0, Math.floor((wallet.available * pct) / 100));
  }

  function setSwapAmount(amount: number) {
    swapAmount = Math.max(1, amount);
  }

  function setMaxSwap() {
    const rate = ORX_RATES[swapAsset] ?? 50;
    const maxUnits = Math.floor((assetBalance("OPT") || 0) / rate);
    swapAmount = Math.max(0, maxUnits);
  }

  async function searchRecipients() {
    recipientBusy = true;
    recipientError = "";
    try {
      recipients = await api.get<typeof recipients>(
        `/wallet/transfer-recipients?q=${encodeURIComponent(recipientQuery)}`,
      );
    } catch (e) {
      recipients = [];
      recipientError = e instanceof ApiError ? e.message : "Gagal mencari penerima";
    } finally {
      recipientBusy = false;
    }
  }
  let recipientError = "";

  async function transfer() {
    transferMsg = "";
    if (!transferTarget || transferAmount <= 0 || transferBusy) return;
    transferBusy = true;
    try {
      await api.post("/wallet/transfers", {
        to_user_id: transferTarget.user_id,
        amount: Number(transferAmount),
        note: transferNote || null,
      });
      transferMsg = `Berhasil mengirim ${transferAmount} OPT ke ${transferTarget.full_name}.`;
      transferAmount = 0;
      transferNote = "";
      transferTarget = null;
      await load();
    } catch (e) {
      transferMsg = e instanceof ApiError ? e.message : "Transfer gagal";
    } finally {
      transferBusy = false;
    }
  }

  async function loadLedger() {
    ledgerLoading = true;
    try {
      ledger = await api.get<LedgerEntry[]>(
        `/wallet/ledger?limit=${PAGE}&offset=${(ledgerPage - 1) * PAGE}`,
      );
      ledgerHasMore = ledger.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat buku besar";
    } finally {
      ledgerLoading = false;
    }
  }

  function goLedger(delta: number) {
    const next = ledgerPage + delta;
    if (next < 1 || (delta > 0 && !ledgerHasMore)) return;
    ledgerPage = next;
    loadLedger();
  }

  async function loadRewards() {
    rewardsLoading = true;
    try {
      rewards = await api.get<Reward[]>(
        `/wallet/rewards?limit=${PAGE}&offset=${(rewardsPage - 1) * PAGE}`,
      );
      rewardsHasMore = rewards.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat hadiah";
    } finally {
      rewardsLoading = false;
    }
  }

  function goRewards(delta: number) {
    const next = rewardsPage + delta;
    if (next < 1 || (delta > 0 && !rewardsHasMore)) return;
    rewardsPage = next;
    loadRewards();
  }

  async function loadTxs() {
    txLoading = true;
    try {
      txs = await api.get<BlockchainTx[]>(
        `/blockchain/transactions?limit=${PAGE}&offset=${(txPage - 1) * PAGE}`,
      );
      txHasMore = txs.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat transaksi";
    } finally {
      txLoading = false;
    }
  }

  function goTxs(delta: number) {
    const next = txPage + delta;
    if (next < 1 || (delta > 0 && !txHasMore)) return;
    txPage = next;
    loadTxs();
  }

  async function load() {
    error = "";
    try {
      wallet = await api.get<Wallet>("/wallet");
      // Seed the editable + withdrawal address from the saved personal wallet.
      walletAddrDraft = wallet.withdrawal_address ?? "";
      if (!withdrawAddr) withdrawAddr = wallet.withdrawal_address ?? "";
      status = await api.get<BlockchainStatus>("/blockchain/status");
      assets = await api.get<WalletAssets>("/wallet/assets");
      await Promise.all([loadLedger(), loadRewards(), loadTxs()]);
      // Keep the header OPT chip in step after swaps/transfers/withdrawals.
      opt.refresh();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat dompet";
    } finally {
      loading = false;
    }
  }

  async function saveWalletAddress(address: string, source: "manual" | "metamask") {
    walletMsg = "";
    error = "";
    walletSaving = true;
    try {
      wallet = await api.patch<Wallet>("/wallet/address", { address, source });
      walletAddrDraft = wallet.withdrawal_address ?? "";
      withdrawAddr = wallet.withdrawal_address ?? withdrawAddr;
      walletMsg =
        source === "metamask"
          ? "Wallet dari MetaMask berhasil disimpan."
          : "Alamat wallet berhasil diperbarui.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyimpan alamat wallet";
    } finally {
      walletSaving = false;
    }
  }

  function saveManualWallet() {
    return saveWalletAddress(walletAddrDraft.trim(), "manual");
  }

  async function connectMetaMask() {
    walletMsg = "";
    error = "";
    try {
      const address = await connectWalletAddress();
      walletAddrDraft = address;
      await saveWalletAddress(address, "metamask");
    } catch (e) {
      error = e instanceof Error ? e.message : "Gagal menghubungkan MetaMask";
    }
  }

  async function withdraw() {
    withdrawMsg = "";
    if (withdrawBusy) return;
    withdrawBusy = true;
    try {
      await api.post("/wallet/withdrawals", {
        amount: Number(withdrawAmount),
        destination_address: withdrawAddr,
      });
      withdrawMsg = "Penarikan diminta. Menunggu persetujuan admin sebelum dikirim ke jaringan.";
      await Promise.all([load(), loadWithdrawals()]);
    } catch (e) {
      withdrawMsg = e instanceof ApiError ? e.message : "Penarikan gagal";
    } finally {
      withdrawBusy = false;
    }
  }

  interface MyWithdrawal {
    id: string;
    amount: number;
    fee_amount: number;
    status: string;
    destination_address: string;
    reject_reason?: string | null;
    created_at: string;
  }
  let withdrawals: MyWithdrawal[] = [];
  let withdrawalFilter: "all" | "requested" | "confirmed" | "rejected" = "all";

  // Human-readable labels for the ledger's reference types.
  const LEDGER_REF_LABELS: Record<string, string> = {
    quest: "Hadiah quest",
    task: "Hadiah tugas",
    exam: "Hadiah ujian",
    reward: "Hadiah",
    swap: "Penukaran aset",
    transfer: "Transfer",
    withdrawal: "Penarikan",
    adjustment: "Penyesuaian admin",
    refund: "Pengembalian dana",
    ai: "Permintaan AI",
    system: "Sistem",
  };
  function ledgerRefLabel(ref: string | null | undefined): string {
    if (!ref) return "Umum";
    return LEDGER_REF_LABELS[ref] ?? ref;
  }

  // Correctness: distinguish the local approval lifecycle labels the backend
  // uses (requested → approved → submitted → confirmed / rejected / cancelled).
  const withdrawalTone: Record<string, string> = {
    requested: "badge-amber",
    approved: "badge-indigo",
    submitted: "badge-indigo",
    confirmed: "badge-mint",
    rejected: "badge-magenta",
    cancelled: "badge-neutral",
    failed: "badge-magenta",
  };

  $: filteredWithdrawals = withdrawals.filter((w) => {
    if (withdrawalFilter === "all") return true;
    if (withdrawalFilter === "requested")
      return w.status === "requested" || w.status === "approved" || w.status === "submitted";
    if (withdrawalFilter === "confirmed") return w.status === "confirmed";
    return w.status === "rejected" || w.status === "cancelled" || w.status === "failed";
  });

  $: pendingWithdrawals = withdrawals.filter(
    (w) => w.status === "requested" || w.status === "approved" || w.status === "submitted",
  ).length;
  $: confirmedWithdrawals = withdrawals.filter((w) => w.status === "confirmed").length;
  $: totalWithdrawn = withdrawals
    .filter((w) => w.status === "confirmed")
    .reduce((s, w) => s + w.amount, 0);

  async function loadWithdrawals() {
    withdrawalsError = "";
    try {
      withdrawals = await api.get<MyWithdrawal[]>("/wallet/withdrawals?limit=20");
    } catch (e) {
      withdrawals = [];
      withdrawalsError = e instanceof ApiError ? e.message : "Gagal memuat riwayat penarikan";
    }
  }
  let withdrawalsError = "";

  async function cancelWithdrawal(id: string) {
    withdrawMsg = "";
    withdrawBusy = true;
    try {
      await api.post(`/wallet/withdrawals/${id}/cancel`);
      withdrawMsg = "Penarikan dibatalkan; dana dikembalikan.";
      await Promise.all([load(), loadWithdrawals()]);
    } catch (e) {
      withdrawMsg = e instanceof ApiError ? e.message : "Gagal membatalkan";
    } finally {
      withdrawBusy = false;
    }
  }

  function swapCost(): number {
    return (ORX_RATES[swapAsset] ?? 0) * Number(swapAmount || 0);
  }

  async function swap() {
    swapMsg = "";
    swapBusy = true;
    try {
      assets = await api.post<WalletAssets>("/wallet/swap", {
        asset: swapAsset,
        amount: Number(swapAmount),
      });
      wallet = await api.get<Wallet>("/wallet");
      swapMsg = `Berhasil menukar ${formatNumber(swapCost())} OPT menjadi ${swapAmount} ${swapAsset}.`;
      swapAmount = 0;
      await Promise.all([loadLedger(), loadRewards(), loadTxs()]);
    } catch (e) {
      swapMsg = e instanceof ApiError ? e.message : "Penukaran gagal";
    } finally {
      swapBusy = false;
    }
  }

  async function payAi() {
    aiMsg = "";
    aiBusy = true;
    try {
      assets = await api.post<WalletAssets>("/wallet/ai-requests", {
        requests: Number(aiRequests),
      });
      aiMsg = `${aiRequests} request AI dibayar dengan ORT.`;
    } catch (e) {
      aiMsg = e instanceof ApiError ? e.message : "Gagal membayar request AI";
    } finally {
      aiBusy = false;
    }
  }

  function assetBalance(asset: string): number {
    return assets?.assets.find((a) => a.asset === asset)?.balance ?? 0;
  }

  onMount(() => {
    metamaskAvailable = hasInjectedWallet();
    load();
    loadWithdrawals();
  });
</script>

<svelte:head><title>Dompet | QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Web3</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Dompet</h1>
  <p class="mt-1 muted">
    Saldo aset digital kustodialmu. Semua reward on-chain masuk ke satu wallet bersama; bagianmu
    terfokus pada akunmu dan dilacak dalam ledger double-entry.
  </p>

  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">
      {error}
    </p>
  {/if}

  {#if loading}
    <div class="mt-6 grid gap-4 sm:grid-cols-3">
      {#each Array(3) as _}<div class="skeleton h-32"></div>{/each}
    </div>
    <div class="mt-6 space-y-2">
      {#each Array(3) as _}<div class="skeleton h-24"></div>{/each}
    </div>
  {:else if !wallet}
    <EmptyState
      tone="error"
      title="Dompet tidak dapat dimuat"
      description={error || "Terjadi kesalahan saat memuat data dompet."}
      actionLabel="Coba lagi"
      onAction={load}
    />
  {:else}
    <div class="mt-6 grid gap-4 sm:grid-cols-3">
      <div class="card">
        <div class="mono-label">Tersedia</div>
        <div class="mt-1 font-display text-3xl font-bold text-highlight">
          {formatNumber(wallet.available)}
        </div>
        <div class="text-xs muted">OPT (token id {wallet.token_id})</div>
        <button
          class="btn-ghost mt-2 !py-1 text-xs"
          on:click={checkReconciliation}
          disabled={reconLoading}
        >
          {reconLoading ? "Memeriksa…" : "Verifikasi saldo"}
        </button>
        {#if recon}
          <p class="mt-1 text-xs" class:alert-ok={recon.ok} class:alert-error={!recon.ok}>
            {recon.ok
              ? "Saldo cocok dengan buku besar."
              : `Selisih: cache ${recon.cached_balance} vs ledger ${recon.computed_balance}`}
          </p>
        {/if}
      </div>
      <div class="card">
        <div class="mono-label">Menunggu</div>
        <div class="mt-1 font-display text-3xl font-bold">{formatNumber(wallet.pending)}</div>
        <div class="text-xs muted">menunggu konfirmasi</div>
      </div>
      <div class="card">
        <div class="mono-label">Jaringan</div>
        <div class="mt-1 font-display text-lg font-bold">{status?.network ?? "-"}</div>
        <div class="text-xs muted">
          {status?.dry_run ? "simulasi (dry-run)" : `chain ${status?.chain_id}`}
        </div>
      </div>
    </div>

    <!-- Settlement lifecycle: what each balance/status actually means -->
    <details class="card mt-4" data-role="settlement-guide">
      <summary class="cursor-pointer font-display font-bold">
        Bagaimana hadiah dan penarikan diselesaikan?
      </summary>
      <div class="mt-3 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <p class="mono-label text-[10px]">Penarikan (withdrawal)</p>
          <ol class="mt-1 space-y-1 text-xs muted">
            <li>
              <strong class="text-ink">Diminta</strong>: pengajuan dibuat, saldo OPT langsung ditahan.
            </li>
            <li><strong class="text-ink">Disetujui</strong>: admin meninjau dan menyetujui.</li>
            <li>
              <strong class="text-ink">Dikirim</strong>: transfer on-chain ke alamat dompet pribadimu.
            </li>
            <li>
              <strong class="text-ink">Terkonfirmasi</strong>: transaksi diterima jaringan; dana ada
              di dompetmu.
            </li>
          </ol>
        </div>
        <div>
          <p class="mono-label text-[10px]">Hadiah (reward)</p>
          <ol class="mt-1 space-y-1 text-xs muted">
            <li>
              <strong class="text-ink">Menunggu</strong>: hadiah tercatat di buku besar, menunggu rantai.
            </li>
            <li>
              <strong class="text-ink">Terkonfirmasi</strong>: transaksi berhasil; saldo risiko nol.
            </li>
            <li>
              <strong class="text-ink">Gagal</strong>: transaksi ditolak; saldo dikembalikan otomatis.
            </li>
            <li>
              <strong class="text-ink">Dibatalkan</strong>: hadiah ditarik kembali (mis. koreksi nilai).
            </li>
          </ol>
        </div>
      </div>
      <p class="mt-3 text-xs muted">
        <Icon name="circle-info" size="11px" class="text-primary" />
        “Verifikasi saldo” memeriksa integritas buku besar (cache vs ledger), bukan konfirmasi pada rantai.
        Saldo baru dianggap final setelah status <strong>terkonfirmasi</strong>.
      </p>
    </details>

    <div class="mt-4 grid gap-4">
      <div class="card">
        <div class="mono-label">Aset digital QLoot</div>
        <p class="mt-1 text-xs muted">
          Tiga aset ERC-1155. Tukar OPT menjadi aset lain lewat
          <span class="text-primary">OryphemProxy (ORX)</span>: 1 ORT = 50 OPT, 1 QTC = 1000 OPT.
        </p>
        <div class="mt-3 grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <span class="badge badge-indigo">OPT</span>
            <p class="mt-1 font-medium">OryphemToken</p>
            <p class="text-xs muted">Mata uang dasar · tanpa batas</p>
            <p class="mt-1 font-mono text-highlight">{formatNumber(assetBalance("OPT"))}</p>
          </div>
          <div>
            <span class="badge badge-indigo">QTC</span>
            <p class="mt-1 font-medium">QlootChain</p>
            <p class="text-xs muted">Sertifikat &amp; pesan terenkripsi · cap 1e15</p>
            <p class="mt-1 font-mono text-highlight">{formatNumber(assetBalance("QTC"))}</p>
          </div>
          <div>
            <span class="badge badge-indigo">ORT</span>
            <p class="mt-1 font-medium">OryphemIntelligence</p>
            <p class="text-xs muted">Kredit AI (1 request = 1 ORT)</p>
            <p class="mt-1 font-mono text-highlight">{formatNumber(assetBalance("ORT"))}</p>
          </div>
        </div>
      </div>

      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Tukar OPT lewat ORX</h2>
        <div class="mt-3 grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <label class="block">
            <span class="mono-label">Aset tujuan</span>
            <select class="input mt-1" bind:value={swapAsset}>
              <option value="ORT">ORT · 50 OPT / unit</option>
              <option value="QTC">QTC · 1000 OPT / unit</option>
            </select>
          </label>
          <label class="block">
            <span class="mono-label">Jumlah ({swapAsset})</span>
            <input class="input mt-1" type="number" min="1" bind:value={swapAmount} />
            <div class="mt-1 flex items-center gap-1 text-[11px]">
              <span class="muted">Preset:</span>
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-1.5 text-[11px]"
                on:click={() => setSwapAmount(1)}>1</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-1.5 text-[11px]"
                on:click={() => setSwapAmount(5)}>5</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-1.5 text-[11px]"
                on:click={() => setSwapAmount(10)}>10</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-1.5 text-[11px] text-primary"
                on:click={setMaxSwap}>Maks</button
              >
            </div>
          </label>
          <button
            class="btn-primary"
            on:click={swap}
            disabled={swapBusy || swapAmount <= 0 || swapCost() > assetBalance("OPT")}
          >
            {swapBusy ? "Memproses…" : `Tukar ${formatNumber(swapCost())} OPT`}
          </button>
        </div>
        <p class="mt-2 text-xs muted">
          Butuh {formatNumber(swapCost())} OPT · tersedia {formatNumber(assetBalance("OPT"))} OPT.
        </p>
        {#if swapMsg}<p class="mt-2 text-sm">{swapMsg}</p>{/if}
      </div>

      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Bayar layanan AI (ORT)</h2>
        <p class="mt-1 text-xs muted">1 request = 1 ORT. ORT dibakar lewat OryphemProxy.</p>
        <div class="mt-3 flex items-end gap-3">
          <label class="block w-32">
            <span class="mono-label">Request</span>
            <input class="input mt-1" type="number" min="1" bind:value={aiRequests} />
          </label>
          <button
            class="btn-secondary"
            on:click={payAi}
            disabled={aiBusy || aiRequests <= 0 || aiRequests > assetBalance("ORT")}
          >
            {aiBusy ? "Memproses…" : "Bayar dengan ORT"}
          </button>
        </div>
        <p class="mt-2 text-xs muted">ORT tersedia: {formatNumber(assetBalance("ORT"))}.</p>
        {#if aiMsg}<p class="mt-2 text-sm">{aiMsg}</p>{/if}
      </div>
    </div>

    <div class="mt-4 grid gap-4">
      <div class="card">
        <div class="mono-label">Saldo terfokus</div>
        <div class="mt-1 flex flex-wrap items-baseline gap-2">
          <span class="font-display text-2xl font-bold text-highlight"
            >{formatNumber(wallet.available)}</span
          >
          <span class="text-sm muted">OPT tersedia</span>
          {#if wallet.withdrawal_address}
            <button
              type="button"
              class="btn-ghost !py-0.5 !px-2 text-xs inline-flex items-center gap-1 font-mono hover:text-primary transition-colors"
              on:click={() => copyToClipboard(wallet?.withdrawal_address ?? "")}
              title="Salin alamat dompet"
              aria-label="Salin alamat dompet penarikan"
            >
              <Icon name={copiedAddr ? "circle-check" : "copy"} size="11px" />
              <span>{copiedAddr ? "Tersalin!" : shortHash(wallet.withdrawal_address, 6)}</span>
            </button>
          {:else}
            <span class="badge badge-neutral text-xs">belum ada alamat pribadi</span>
          {/if}
        </div>
        {#if copyError}
          <p class="mt-1 text-xs text-danger" role="alert" aria-live="assertive">{copyError}</p>
        {/if}
        <div class="mt-1 text-xs muted">
          Reward kredit dikreditkan ke akunmu lewat ledger double-entry dan bisa ditarik ke wallet
          pribadimu kapan saja.
        </div>
      </div>
    </div>

    <div class="card mt-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="hud font-display text-lg font-bold">Wallet saya</h2>
        <span class="mono-label">Alamat yang dipakai untuk penarikan</span>
      </div>
      <p class="mt-1 text-xs muted">
        Ini wallet pribadimu: semua penarikan akan dikirim ke alamat ini. Tempel alamatnya
        langsung, atau hubungkan lewat MetaMask. Semua akun memakai alamat default platform sampai
        kamu menggantinya.
      </p>

      <div class="mt-3 flex flex-wrap items-end gap-2">
        <label class="block min-w-[260px] flex-1">
          <span class="mono-label">Alamat wallet (0x…)</span>
          <input
            class="input mt-1 font-mono"
            placeholder="0x…"
            maxlength="42"
            bind:value={walletAddrDraft}
          />
        </label>
        <button
          class="btn-primary"
          on:click={saveManualWallet}
          disabled={walletSaving || walletAddrDraft.trim().length !== 42}
        >
          {walletSaving ? "Menyimpan…" : "Simpan alamat"}
        </button>
        <button class="btn-secondary" on:click={connectMetaMask} disabled={walletSaving}>
          <Icon name="wallet" size="12px" /> Hubungkan MetaMask
        </button>
      </div>

      {#if !metamaskAvailable}
        <p class="mt-2 text-xs muted">
          <Icon name="circle-info" size="10px" /> MetaMask belum terdeteksi di peramban ini: kamu tetap
          bisa menempelkan alamat secara manual.
        </p>
      {/if}
      {#if walletMsg}<p class="alert-ok mt-3 text-sm">{walletMsg}</p>{/if}
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Tarik ke dompet pribadi</h2>
        <div class="mt-3 space-y-3">
          <div>
            <input
              class="input"
              type="number"
              min="1"
              placeholder="Jumlah (OPT)"
              aria-label="Jumlah penarikan (OPT)"
              bind:value={withdrawAmount}
            />
            <div class="mt-1 flex items-center gap-1.5 text-xs">
              <span class="muted">Cepat:</span>
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-2 text-xs"
                on:click={() => setWithdrawPercent(25)}>25%</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-2 text-xs"
                on:click={() => setWithdrawPercent(50)}>50%</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-2 text-xs"
                on:click={() => setWithdrawPercent(75)}>75%</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-2 text-xs text-primary font-medium"
                on:click={() => setWithdrawPercent(100)}>Maks</button
              >
            </div>
          </div>
          <label class="block">
            <span class="mono-label">Kirim ke wallet</span>
            <input
              class="input mt-1 font-mono"
              placeholder="0x…"
              bind:value={withdrawAddr}
              maxlength="42"
            />
          </label>
          {#if wallet}
            <button
              class="btn-ghost !py-1 text-xs"
              on:click={() => (withdrawAddr = wallet?.withdrawal_address ?? "")}
              disabled={withdrawAddr === wallet.withdrawal_address}
            >
              <Icon name="wallet" size="11px" /> Pakai wallet saya
            </button>
          {/if}
          <button
            class="btn-primary"
            on:click={withdraw}
            disabled={withdrawBusy || withdrawAmount <= 0 || withdrawAddr.length !== 42}
            >{withdrawBusy ? "Memproses…" : "Minta penarikan"}</button
          >
          {#if withdrawMsg}<p class="text-sm muted" role="status" aria-live="polite">
              {withdrawMsg}
            </p>{/if}
        </div>
        {#if withdrawalsError}
          <div class="mt-4 border-t pt-4">
            <p class="text-sm text-danger" role="alert" aria-live="assertive">
              <Icon name="triangle-exclamation" size="12px" class="mt-0.5 inline-flex" />
              {withdrawalsError}
            </p>
            <button class="btn-ghost mt-2 !py-1 text-xs" on:click={loadWithdrawals}
              >Coba lagi</button
            >
          </div>
        {:else if withdrawals.length}
          <div class="mt-4 border-t pt-4">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="mono-label">Riwayat penarikan</p>
              <span class="mono-label text-[10px]">
                {confirmedWithdrawals} selesai · {formatNumber(totalWithdrawn)} OPT
              </span>
            </div>

            <!-- Status filter chips -->
            <div class="mt-2 flex flex-wrap gap-1 text-xs">
              {#each [["all", `Semua (${withdrawals.length})`], ["requested", `Diproses (${pendingWithdrawals})`], ["confirmed", `Selesai (${confirmedWithdrawals})`], ["rejected", "Gagal/Ditolak"]] as [val, label]}
                <button
                  type="button"
                  class="btn-pill !py-1 text-xs"
                  class:!border-primary={withdrawalFilter === val}
                  class:!text-primary={withdrawalFilter === val}
                  on:click={() => (withdrawalFilter = val as typeof withdrawalFilter)}
                >
                  {label}
                </button>
              {/each}
            </div>

            {#if filteredWithdrawals.length === 0}
              <p class="mt-3 text-xs muted">Tidak ada penarikan dengan status ini.</p>
            {:else}
              <ul class="mt-3 space-y-2">
                {#each filteredWithdrawals as w (w.id)}
                  <li class="flex items-center justify-between gap-3 text-sm">
                    <span class="min-w-0">
                      <span class="font-mono">{formatNumber(w.amount)} OPT</span>
                      <span class="ml-2 badge {withdrawalTone[w.status] ?? 'badge-neutral'}"
                        >{statusLabel(w.status)}</span
                      >
                      <span class="block text-[11px] muted mt-0.5"
                        >{relativeTime(w.created_at)} ·
                        <span class="font-mono">{w.destination_address.slice(0, 10)}…</span></span
                      >
                      {#if w.reject_reason}
                        <span class="block text-xs text-tertiary">{w.reject_reason}</span>
                      {/if}
                    </span>
                    {#if w.status === "requested"}
                      <button
                        class="btn-ghost !py-1 text-xs shrink-0"
                        on:click={() => cancelWithdrawal(w.id)}
                        disabled={withdrawBusy}>Batalkan</button
                      >
                    {/if}
                  </li>
                {/each}
              </ul>
            {/if}
          </div>
        {/if}
      </div>

      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Kirim OPT ke pengguna lain</h2>
        <div class="mt-3 space-y-3">
          {#if transferTarget}
            <div class="flex items-center justify-between rounded-sm border px-3 py-2 text-sm">
              <span>
                <span class="font-medium">{transferTarget.full_name}</span>
                <span class="block text-xs muted"
                  >{transferTarget.handle} · {transferTarget.email_masked}</span
                >
              </span>
              <button class="btn-ghost !py-1 text-xs" on:click={() => (transferTarget = null)}
                >Ganti</button
              >
            </div>
          {:else}
            <div class="flex items-center gap-2">
              <input
                class="input"
                placeholder="Cari nama atau email…"
                aria-label="Cari penerima transfer"
                bind:value={recipientQuery}
                on:keydown={(e) => e.key === "Enter" && searchRecipients()}
              />
              <button
                class="btn-secondary flex-none"
                on:click={searchRecipients}
                disabled={recipientBusy}>{recipientBusy ? "Mencari…" : "Cari"}</button
              >
            </div>
            {#if recipientError}
              <p class="mt-1 text-xs text-danger" role="alert" aria-live="assertive">
                {recipientError}
              </p>
            {:else if recipients.length}
              <ul class="max-h-40 space-y-1 overflow-y-auto">
                {#each recipients as r}
                  <li>
                    <button
                      class="flex w-full items-center justify-between rounded-sm border px-3 py-1.5 text-left text-sm transition-colors hover:border-primary"
                      on:click={() => {
                        transferTarget = r;
                        recipients = [];
                        recipientQuery = "";
                      }}
                    >
                      <span>{r.full_name}</span>
                      <span class="text-xs muted">{r.email_masked}</span>
                    </button>
                  </li>
                {/each}
              </ul>
            {:else if recipientQuery.trim() && !recipientBusy}
              <p class="mt-1 text-xs muted">Penerima tidak ditemukan.</p>
            {/if}
          {/if}
          <div>
            <input
              class="input"
              type="number"
              min="1"
              placeholder="Jumlah (OPT)"
              aria-label="Jumlah transfer (OPT)"
              bind:value={transferAmount}
            />
            <div class="mt-1 flex items-center gap-1.5 text-xs">
              <span class="muted">Cepat:</span>
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-2 text-xs"
                on:click={() => setTransferPercent(25)}>25%</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-2 text-xs"
                on:click={() => setTransferPercent(50)}>50%</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-2 text-xs"
                on:click={() => setTransferPercent(75)}>75%</button
              >
              <button
                type="button"
                class="btn-ghost !py-0.5 !px-2 text-xs text-primary font-medium"
                on:click={() => setTransferPercent(100)}>Maks</button
              >
            </div>
          </div>
          <input
            class="input"
            placeholder="Catatan (opsional)"
            aria-label="Catatan transfer (opsional)"
            maxlength="255"
            bind:value={transferNote}
          />
          <button
            class="btn-primary"
            on:click={transfer}
            disabled={transferBusy || !transferTarget || transferAmount <= 0}
            >{transferBusy ? "Mengirim…" : "Kirim"}</button
          >
          {#if transferMsg}<p class="text-sm muted" role="status" aria-live="polite">
              {transferMsg}
            </p>{/if}
        </div>
      </div>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Hadiah terbaru</h2>
        <ul class="mt-2 space-y-2 text-sm">
          {#each rewards as r (r.id)}
            <li class="flex items-center justify-between border-b pb-1 last:border-0">
              <span>
                <span class="font-medium">{ledgerRefLabel(r.reward_type)}</span>
                {#if r.rank}<span class="muted">#{r.rank}</span>{/if}
                <span class="block text-[11px] muted">{relativeTime(r.created_at)}</span>
              </span>
              <span class="flex items-center gap-2">
                <span class="font-mono text-highlight">+{formatNumber(r.amount)}</span>
                <span
                  class="badge"
                  class:badge-mint={r.status === "confirmed"}
                  class:badge-amber={r.status !== "confirmed"}>{statusLabel(r.status)}</span
                >
              </span>
            </li>
          {/each}
          {#if rewards.length === 0}<li class="muted">Belum ada hadiah.</li>{/if}
        </ul>
        <Pagination
          page={rewardsPage}
          pageSize={PAGE}
          hasMore={rewardsHasMore}
          loading={rewardsLoading}
          label="hadiah"
          onPrev={() => goRewards(-1)}
          onNext={() => goRewards(1)}
        />
      </div>
    </div>

    <div class="card mt-4">
      <div class="flex items-center justify-between">
        <h2 class="hud font-display text-lg font-bold">Buku besar</h2>
        <span class="mono-label text-[10px]">{ledger.length} entri terbaru</span>
      </div>
      <div class="mt-2 overflow-x-auto">
        <table class="w-full text-sm">
          <caption class="sr-only">Buku besar dompet</caption>
          <thead class="text-left muted">
            <tr
              ><th class="py-1" scope="col">Tanggal</th><th scope="col">Tipe</th><th scope="col"
                >Keterangan</th
              ><th scope="col">Jumlah</th><th class="text-right" scope="col">Saldo</th></tr
            >
          </thead>
          <tbody>
            {#each ledger as entry (entry.id)}
              {@const isCredit = entry.entry_type === "credit"}
              <tr class="border-t">
                <td class="py-1 text-xs muted whitespace-nowrap">{formatDate(entry.created_at)}</td>
                <td>
                  <span class="badge" class:badge-mint={isCredit} class:badge-magenta={!isCredit}>
                    {isCredit ? "Masuk" : "Keluar"}
                  </span>
                </td>
                <td class="text-xs">
                  <span class="font-medium">{ledgerRefLabel(entry.reference_type)}</span>
                  {#if entry.description}
                    <span class="block muted">{entry.description}</span>
                  {/if}
                </td>
                <td
                  class="font-mono"
                  class:text-secondary={isCredit}
                  class:text-tertiary={!isCredit}
                >
                  {isCredit ? "+" : "-"}{formatNumber(entry.amount)}
                </td>
                <td class="text-right font-mono">{formatNumber(entry.balance_after)}</td>
              </tr>
            {/each}
            {#if ledger.length === 0}<tr
                ><td colspan="5" class="py-2 muted">Buku besar kosong.</td></tr
              >{/if}
          </tbody>
        </table>
      </div>
      <Pagination
        page={ledgerPage}
        pageSize={PAGE}
        hasMore={ledgerHasMore}
        loading={ledgerLoading}
        label="entri buku besar"
        onPrev={() => goLedger(-1)}
        onNext={() => goLedger(1)}
      />
    </div>

    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Transaksi on-chain</h2>
      <ul class="mt-2 space-y-2 text-sm">
        {#each txs as tx}
          {@const url = tx.explorer_url ?? etherscanUrl(tx.transaction_hash, status?.chain_id)}
          <li class="flex flex-wrap items-center justify-between gap-2 border-b pb-2 last:border-0">
            <span>
              <span
                class="badge"
                class:badge-mint={tx.status === "confirmed"}
                class:badge-amber={tx.status !== "confirmed"}>{statusLabel(tx.status)}</span
              >
              <span class="ml-2">{tx.method}</span>
            </span>
            <span class="font-mono text-xs">
              {#if url}
                <a class="text-primary" href={url} target="_blank" rel="noopener noreferrer"
                  >{shortHash(tx.transaction_hash)} ↗</a
                >
              {:else}
                {shortHash(tx.transaction_hash)}
              {/if}
              · {tx.confirmation_count} conf
            </span>
          </li>
        {/each}
        {#if txs.length === 0}<li class="muted">Belum ada transaksi.</li>{/if}
      </ul>
      <Pagination
        page={txPage}
        pageSize={PAGE}
        hasMore={txHasMore}
        loading={txLoading}
        label="transaksi"
        onPrev={() => goTxs(-1)}
        onNext={() => goTxs(1)}
      />
    </div>
  {/if}
</div>
