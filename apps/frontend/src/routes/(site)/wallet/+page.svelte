<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Wallet, LedgerEntry, Reward, BlockchainStatus, BlockchainTx } from "$lib/types";
  import {
    formatDate,
    formatNumber,
    shortHash,
    etherscanUrl,
    statusLabel,
  } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { connectWalletAddress, hasInjectedWallet } from "$lib/utils/metamask";

  const PAGE = 10;
  let wallet: Wallet | null = null;
  let ledger: LedgerEntry[] = [];
  let rewards: Reward[] = [];
  let status: BlockchainStatus | null = null;
  let txs: BlockchainTx[] = [];
  let loading = true;
  let error = "";
  let withdrawAmount = 0;
  let withdrawAddr = "";
  let withdrawMsg = "";

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
  let recipients: { user_id: string; full_name: string; email: string }[] = [];
  let recipientQuery = "";
  let recipientBusy = false;
  let transferTarget: { user_id: string; full_name: string; email: string } | null = null;
  let transferAmount = 0;
  let transferNote = "";
  let transferMsg = "";

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
    if (!transferTarget || transferAmount <= 0) return;
    try {
      await api.post("/wallet/transfers", {
        to_user_id: transferTarget.user_id,
        amount: Number(transferAmount),
        note: transferNote || null,
      });
      transferMsg = `Berhasil mengirim ${transferAmount} OPC ke ${transferTarget.full_name}.`;
      transferAmount = 0;
      transferNote = "";
      transferTarget = null;
      await load();
    } catch (e) {
      transferMsg = e instanceof ApiError ? e.message : "Transfer gagal";
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
      await Promise.all([loadLedger(), loadRewards(), loadTxs()]);
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
    try {
      await api.post("/wallet/withdrawals", {
        amount: Number(withdrawAmount),
        destination_address: withdrawAddr,
      });
      withdrawMsg = "Penarikan diminta dan dimasukkan ke antrean worker blockchain.";
      await load();
    } catch (e) {
      withdrawMsg = e instanceof ApiError ? e.message : "Penarikan gagal";
    }
  }

  onMount(() => {
    metamaskAvailable = hasInjectedWallet();
    load();
  });
</script>

<svelte:head><title>Dompet — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Web3</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Dompet</h1>
  <p class="mt-1 muted">
    Saldo OPC kustodialmu. Semua reward on-chain masuk ke satu wallet bersama; bagianmu terfokus
    pada akunmu dan dilacak dalam ledger double-entry.
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
        <div class="text-xs muted">OPC (token id {wallet.token_id})</div>
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
        <div class="mono-label">Saldo terfokus</div>
        <div class="mt-1 flex flex-wrap items-baseline gap-2">
          <span class="font-display text-2xl font-bold text-highlight"
            >{formatNumber(wallet.available)}</span
          >
          <span class="text-sm muted">OPC tersedia</span>
          {#if wallet.withdrawal_address}
            <span class="badge badge-indigo font-mono text-xs"
              >→ {shortHash(wallet.withdrawal_address, 6)}</span
            >
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
        Ini wallet pribadimu — semua penarikan OPC akan dikirim ke alamat ini. Tempel alamatnya
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
          <input
            class="input"
            type="number"
            min="1"
            placeholder="Jumlah (OPC)"
            bind:value={withdrawAmount}
          />
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
            disabled={withdrawAmount <= 0 || withdrawAddr.length !== 42}>Minta penarikan</button
          >
          {#if withdrawMsg}<p class="text-sm muted">{withdrawMsg}</p>{/if}
        </div>
      </div>

      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Kirim OPC ke pengguna lain</h2>
        <div class="mt-3 space-y-3">
          {#if transferTarget}
            <div class="flex items-center justify-between rounded-sm border px-3 py-2 text-sm">
              <span>
                <span class="font-medium">{transferTarget.full_name}</span>
                <span class="block text-xs muted">{transferTarget.email}</span>
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
                      <span class="text-xs muted">{r.email}</span>
                    </button>
                  </li>
                {/each}
              </ul>
            {/if}
          {/if}
          <input
            class="input"
            type="number"
            min="1"
            placeholder="Jumlah (OPC)"
            bind:value={transferAmount}
          />
          <input class="input" placeholder="Catatan (opsional)" bind:value={transferNote} />
          <button
            class="btn-primary"
            on:click={transfer}
            disabled={!transferTarget || transferAmount <= 0}>Kirim</button
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
