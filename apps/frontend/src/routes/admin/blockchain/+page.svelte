<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { BlockchainStatus, BlockchainTx } from "$lib/types";
  import { formatDate, shortHash, etherscanUrl } from "$lib/utils/format";

  let status: BlockchainStatus | null = null;
  let txs: BlockchainTx[] = [];
  let events: { name: string; transaction_hash: string; block_number: number; args: Record<string, unknown> }[] = [];
  let message = "";
  let error = "";

  async function load() {
    try {
      status = await api.get<BlockchainStatus>("/blockchain/status");
      txs = await api.get<BlockchainTx[]>("/blockchain/transactions");
      events = await api.get("/blockchain/events");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load blockchain data";
    }
  }

  async function control(action: "pause" | "unpause") {
    await api.post(`/admin/blockchain/${action}`);
    message = `${action} queued for the blockchain worker`;
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>Blockchain — QLoot Admin</title></svelte:head>

<h1 class="text-2xl font-bold">Blockchain</h1>

{#if message}<p class="mt-4 rounded-lg bg-primary-50 p-3 text-sm dark:bg-slate-800">{message}</p>{/if}
{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>
{/if}

{#if status}
  <div class="card mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
    <div><div class="text-sm muted">Network</div><div class="font-semibold">{status.network}</div></div>
    <div><div class="text-sm muted">Chain ID</div><div class="font-semibold">{status.chain_id}</div></div>
    <div><div class="text-sm muted">Mode</div><div class="font-semibold">{status.dry_run ? "dry-run" : "live"}</div></div>
    <div><div class="text-sm muted">Confirmations</div><div class="font-semibold">{status.confirmations_required}</div></div>
    <div class="sm:col-span-2">
      <div class="text-sm muted">Contract</div>
      <div class="break-all font-mono text-xs">{status.contract_address ?? "not deployed"}</div>
    </div>
    <div class="sm:col-span-2">
      <div class="text-sm muted">Treasury</div>
      <div class="break-all font-mono text-xs">{status.treasury_address ?? "not set"}</div>
    </div>
  </div>

  <div class="mt-4 flex gap-2">
    <button class="btn-ghost" on:click={() => control("pause")}>Pause rewards</button>
    <button class="btn-primary" on:click={() => control("unpause")}>Unpause rewards</button>
  </div>
{/if}

<div class="card mt-4">
  <h2 class="font-semibold">Transactions</h2>
  <div class="mt-2 overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="text-left muted">
        <tr><th class="py-1">Method</th><th>Status</th><th>Hash</th><th class="text-right">Conf</th><th class="text-right">When</th></tr>
      </thead>
      <tbody>
        {#each txs as tx}
          {@const url = tx.explorer_url ?? etherscanUrl(tx.transaction_hash, status?.chain_id)}
          <tr class="border-t">
            <td class="py-1">{tx.method}</td>
            <td><span class="badge" class:bg-green-100={tx.status === "confirmed"} class:text-green-700={tx.status === "confirmed"}>{tx.status}</span></td>
            <td class="font-mono text-xs">
              {#if url}<a class="text-primary-600" href={url} target="_blank" rel="noopener noreferrer">{shortHash(tx.transaction_hash)} ↗</a>
              {:else}{shortHash(tx.transaction_hash)}{/if}
            </td>
            <td class="text-right">{tx.confirmation_count}</td>
            <td class="text-right text-xs muted">{formatDate(tx.created_at)}</td>
          </tr>
        {/each}
        {#if txs.length === 0}<tr><td colspan="5" class="py-2 muted">No transactions.</td></tr>{/if}
      </tbody>
    </table>
  </div>
</div>

<div class="card mt-4">
  <h2 class="font-semibold">Recent events</h2>
  <ul class="mt-2 space-y-1 text-xs font-mono">
    {#each events.slice(0, 15) as e}
      <li class="muted">[{e.block_number}] {e.name} · {shortHash(e.transaction_hash)}</li>
    {/each}
    {#if events.length === 0}<li class="muted">No events indexed.</li>{/if}
  </ul>
</div>
