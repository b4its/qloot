<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Wallet, LedgerEntry, Reward, BlockchainStatus, BlockchainTx } from "$lib/types";
  import { formatDate, formatNumber, shortHash, etherscanUrl } from "$lib/utils/format";

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

  async function load() {
    try {
      wallet = await api.get<Wallet>("/wallet");
      ledger = await api.get<LedgerEntry[]>("/wallet/ledger");
      rewards = await api.get<Reward[]>("/wallet/rewards");
      status = await api.get<BlockchainStatus>("/blockchain/status");
      txs = await api.get<BlockchainTx[]>("/blockchain/transactions");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load wallet";
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
      withdrawMsg = "Withdrawal requested and queued for the blockchain worker.";
      await load();
    } catch (e) {
      withdrawMsg = e instanceof ApiError ? e.message : "Withdrawal failed";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Wallet — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Wallet</h1>
<p class="mt-1 muted">
  Your custodial OPC balance. Treasury holds tokens on-chain; your balance is tracked in a
  double-entry ledger.
</p>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-tertiary dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading wallet…</p>
{:else if wallet}
  <div class="mt-4 grid gap-4 sm:grid-cols-3">
    <div class="card">
      <div class="text-sm muted">Available</div>
      <div class="text-3xl font-bold text-highlight">{formatNumber(wallet.available)}</div>
      <div class="text-xs muted">OPC (token id {wallet.token_id})</div>
    </div>
    <div class="card">
      <div class="text-sm muted">Pending</div>
      <div class="text-3xl font-bold">{formatNumber(wallet.pending)}</div>
      <div class="text-xs muted">awaiting confirmation</div>
    </div>
    <div class="card">
      <div class="text-sm muted">Network</div>
      <div class="text-lg font-semibold">{status?.network ?? "—"}</div>
      <div class="text-xs muted">
        {status?.dry_run ? "simulation (dry-run)" : `chain ${status?.chain_id}`}
      </div>
    </div>
  </div>

  <div class="mt-4 grid gap-4 lg:grid-cols-2">
    <div class="card">
      <h2 class="font-semibold">Withdraw to a personal wallet</h2>
      <div class="mt-3 space-y-3">
        <input
          class="input"
          type="number"
          min="1"
          placeholder="Amount (OPC)"
          bind:value={withdrawAmount}
        />
        <input class="input font-mono" placeholder="0x…" bind:value={withdrawAddr} maxlength="42" />
        <button
          class="btn-primary"
          on:click={withdraw}
          disabled={withdrawAmount <= 0 || withdrawAddr.length !== 42}>Request withdrawal</button
        >
        {#if withdrawMsg}<p class="text-sm muted">{withdrawMsg}</p>{/if}
      </div>
    </div>

    <div class="card">
      <h2 class="font-semibold">Recent rewards</h2>
      <ul class="mt-2 space-y-2 text-sm">
        {#each rewards.slice(0, 6) as r}
          <li class="flex items-center justify-between">
            <span>{r.reward_type}{r.rank ? ` #${r.rank}` : ""}</span>
            <span class="flex items-center gap-2">
              <span class="font-mono text-highlight">+{r.amount}</span>
              <span
                class="badge"
                class:bg-green-100={r.status === "confirmed"}
                class:text-secondary={r.status === "confirmed"}>{r.status}</span
              >
            </span>
          </li>
        {/each}
        {#if rewards.length === 0}<li class="muted">No rewards yet.</li>{/if}
      </ul>
    </div>
  </div>

  <div class="card mt-4">
    <h2 class="font-semibold">Ledger</h2>
    <div class="mt-2 overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">Date</th><th>Type</th><th>Amount</th><th class="text-right"
              >Balance</th
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
          {#if ledger.length === 0}<tr><td colspan="4" class="py-2 muted">Empty ledger.</td></tr
            >{/if}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card mt-4">
    <h2 class="font-semibold">On-chain transactions</h2>
    <ul class="mt-2 space-y-2 text-sm">
      {#each txs.slice(0, 10) as tx}
        {@const url = tx.explorer_url ?? etherscanUrl(tx.transaction_hash, status?.chain_id)}
        <li class="flex flex-wrap items-center justify-between gap-2">
          <span>
            <span
              class="badge"
              class:bg-green-100={tx.status === "confirmed"}
              class:text-secondary={tx.status === "confirmed"}>{tx.status}</span
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
      {#if txs.length === 0}<li class="muted">No transactions yet.</li>{/if}
    </ul>
  </div>
{/if}
