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

  async function load() {
    try {
      wallet = await api.get<Wallet>("/wallet");
      ledger = await api.get<LedgerEntry[]>("/wallet/ledger");
      rewards = await api.get<Reward[]>("/wallet/rewards");
      status = await api.get<BlockchainStatus>("/blockchain/status");
      txs = await api.get<BlockchainTx[]>("/blockchain/transactions");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat dompet";
    } finally {
      loading = false;
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

  onMount(load);
</script>

<svelte:head><title>Dompet — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Web3</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Dompet</h1>
  <p class="mt-1 muted">
    Saldo OPC kustodialmu. Treasury memegang token on-chain; saldomu dilacak dalam ledger
    double-entry.
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
          <input
            class="input font-mono"
            placeholder="0x…"
            bind:value={withdrawAddr}
            maxlength="42"
          />
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
          {#each rewards.slice(0, 6) as r}
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
            {#each ledger.slice(0, 12) as entry}
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
    </div>

    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Transaksi on-chain</h2>
      <ul class="mt-2 space-y-2 text-sm">
        {#each txs.slice(0, 10) as tx}
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
    </div>
  {/if}
</div>
