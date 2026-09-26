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
    shortHash,
    etherscanUrl,
    statusLabel,
  } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import Icon from "$lib/components/Icon.svelte";
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
  async function copyToClipboard(text: string) {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      copiedAddr = true;
      setTimeout(() => (copiedAddr = false), 2000);
    } catch {}
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
    try {
      recipients = await api.get<typeof recipients>(
        `/wallet/transfer-recipients?q=${encodeURIComponent(recipientQuery)}`,
      );
    } catch {
      recipients = [];
    } finally {
      recipientBusy = false;
    }
  }

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

  async function loadWithdrawals() {
    try {
      withdrawals = await api.get<MyWithdrawal[]>("/wallet/withdrawals?limit=20");
    } catch {
      withdrawals = [];
    }
  }

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

<svelte:head><title>Dompet — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Web3</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Dompet</h1>
  <p class="mt-1 muted">
    Saldo aset digital kustodialmu. Semua reward on-chain masuk ke satu wallet bersama; bagianmu
    terfokus pada akunmu dan dilacak dalam ledger double-entry.
  </p>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  {#if loading}
    <p class="mt-6 muted">Memuat dompet…</p>
  {:else if wallet}
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
        <div class="mt-1 font-display text-lg font-bold">{status?.network ?? "—"}</div>
        <div class="text-xs muted">
          {status?.dry_run ? "simulasi (dry-run)" : `chain ${status?.chain_id}`}
        </div>
      </div>
    </div>

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
            >
              <Icon name={copiedAddr ? "circle-check" : "copy"} size="11px" />
              <span>{copiedAddr ? "Tersalin!" : shortHash(wallet.withdrawal_address, 6)}</span>
            </button>
          {:else}
            <span class="badge badge-neutral text-xs">belum ada alamat pribadi</span>
          {/if}
        </div>
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
        Ini wallet pribadimu — semua penarikan akan dikirim ke alamat ini. Tempel alamatnya
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
          <Icon name="circle-info" size="10px" /> MetaMask belum terdeteksi di peramban ini — kamu tetap
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
          {#if withdrawMsg}<p class="text-sm muted">{withdrawMsg}</p>{/if}
        </div>
        {#if withdrawals.length}
          <div class="mt-4 border-t pt-4">
            <p class="mono-label mb-2">Riwayat penarikan</p>
            <ul class="space-y-2">
              {#each withdrawals as w}
                <li class="flex items-center justify-between gap-3 text-sm">
                  <span>
                    <span class="font-mono">{formatNumber(w.amount)} OPT</span>
                    <span class="ml-2 badge badge-slate">{w.status}</span>
                    {#if w.reject_reason}
                      <span class="ml-2 text-xs muted">{w.reject_reason}</span>
                    {/if}
                  </span>
                  {#if w.status === "requested"}
                    <button
                      class="btn-ghost !py-1 text-xs"
                      on:click={() => cancelWithdrawal(w.id)}
                      disabled={withdrawBusy}>Batalkan</button
                    >
                  {/if}
                </li>
              {/each}
            </ul>
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
                bind:value={recipientQuery}
                on:keydown={(e) => e.key === "Enter" && searchRecipients()}
              />
              <button
                class="btn-secondary flex-none"
                on:click={searchRecipients}
                disabled={recipientBusy}>Cari</button
              >
            </div>
            {#if recipients.length}
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
            {/if}
          {/if}
          <div>
            <input
              class="input"
              type="number"
              min="1"
              placeholder="Jumlah (OPT)"
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
          <input class="input" placeholder="Catatan (opsional)" bind:value={transferNote} />
          <button
            class="btn-primary"
            on:click={transfer}
            disabled={transferBusy || !transferTarget || transferAmount <= 0}
            >{transferBusy ? "Mengirim…" : "Kirim"}</button
          >
          {#if transferMsg}<p class="text-sm muted">{transferMsg}</p>{/if}
        </div>
      </div>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Hadiah terbaru</h2>
        <ul class="mt-2 space-y-2 text-sm">
          {#each rewards as r}
            <li class="flex items-center justify-between border-b pb-1 last:border-0">
              <span>{r.reward_type}{r.rank ? ` #${r.rank}` : ""}</span>
              <span class="flex items-center gap-2">
                <span class="font-mono text-highlight">+{r.amount}</span>
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
      <h2 class="hud font-display text-lg font-bold">Buku besar</h2>
      <div class="mt-2 overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left muted">
            <tr
              ><th class="py-1">Tanggal</th><th>Tipe</th><th>Jumlah</th><th class="text-right"
                >Saldo</th
              ></tr
            >
          </thead>
          <tbody>
            {#each ledger as entry}
              <tr class="border-t">
                <td class="py-1 text-xs muted">{formatDate(entry.created_at)}</td>
                <td>
                  <span class:text-tertiary={entry.entry_type === "debit"}>{entry.entry_type}</span>
                  <span class="text-xs muted"> · {entry.reference_type}</span>
                </td>
                <td class="font-mono" class:text-secondary={entry.entry_type === "credit"}>
                  {entry.entry_type === "debit" ? "-" : "+"}{entry.amount}
                </td>
                <td class="text-right font-mono">{formatNumber(entry.balance_after)}</td>
              </tr>
            {/each}
            {#if ledger.length === 0}<tr
                ><td colspan="4" class="py-2 muted">Buku besar kosong.</td></tr
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
