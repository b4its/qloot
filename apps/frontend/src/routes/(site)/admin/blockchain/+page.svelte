<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { BlockchainStatus, BlockchainTx } from "$lib/types";
  import { formatDate, shortHash, etherscanUrl } from "$lib/utils/format";

  let status: BlockchainStatus | null = null;
  let txs: BlockchainTx[] = [];
  let events: {
    name: string;
    transaction_hash: string;
    block_number: number;
    args: Record<string, unknown>;
  }[] = [];
  let message = "";
  let error = "";
  let loading = true;
  let busy = "";

  async function load() {
    loading = true;
    error = "";
    try {
      status = await api.get<BlockchainStatus>("/blockchain/status");
      txs = await api.get<BlockchainTx[]>("/blockchain/transactions?limit=100");
      events = await api.get("/blockchain/events?limit=50");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat data blockchain";
    } finally {
      loading = false;
    }
  }

  async function control(action: "pause" | "unpause") {
    error = "";
    message = "";
    busy = action;
    try {
      await api.post(`/admin/blockchain/${action}`);
      message = `${action} diantrekan untuk blockchain worker`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim perintah";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Blockchain — QLoot Admin</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Admin · Blockchain</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Blockchain</h1>
  <p class="mt-2 muted">Status kontrak, transaksi, dan event on-chain OryphemCoin.</p>

  {#if message}<p class="alert-ok mt-4">
      {message}
    </p>{/if}
  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  {#if status}
    <div class="card mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <div class="mono-label">Network</div>
        <div class="font-semibold">{status.network}</div>
      </div>
      <div>
        <div class="mono-label">Chain ID</div>
        <div class="font-semibold">{status.chain_id}</div>
      </div>
      <div>
        <div class="mono-label">Mode</div>
        <div class="font-semibold">{status.dry_run ? "dry-run" : "live"}</div>
      </div>
      <div>
        <div class="mono-label">Confirmations</div>
        <div class="font-semibold">{status.confirmations_required}</div>
      </div>
      <div class="sm:col-span-2">
        <div class="mono-label">Contract</div>
        <div class="break-all font-mono text-xs">{status.contract_address ?? "not deployed"}</div>
      </div>
      <div class="sm:col-span-2">
        <div class="mono-label">Treasury</div>
        <div class="break-all font-mono text-xs">{status.treasury_address ?? "not set"}</div>
      </div>
    </div>

    <div class="mt-4 flex gap-2">
      <button class="btn-ghost" on:click={() => control("pause")}>Pause rewards</button>
      <button class="btn-primary" on:click={() => control("unpause")}>Unpause rewards</button>
    </div>
  {/if}

  <div class="card mt-4">
    <h2 class="hud font-display text-lg font-bold">Transactions</h2>
    <div class="mt-2 overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">Method</th><th>Status</th><th>Hash</th><th class="text-right">Conf</th
            ><th class="text-right">When</th></tr
          >
        </thead>
        <tbody>
          {#each txs as tx}
            {@const url = tx.explorer_url ?? etherscanUrl(tx.transaction_hash, status?.chain_id)}
            <tr class="border-t">
              <td class="py-1">{tx.method}</td>
              <td
                ><span
                  class="badge"
                  class:badge-mint={tx.status === "confirmed"}
                  class:badge-amber={tx.status !== "confirmed"}>{tx.status}</span
                ></td
              >
              <td class="font-mono text-xs">
                {#if url}<a
                    class="text-primary"
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer">{shortHash(tx.transaction_hash)} ↗</a
                  >
                {:else}{shortHash(tx.transaction_hash)}{/if}
              </td>
              <td class="text-right">{tx.confirmation_count}</td>
              <td class="text-right text-xs muted">{formatDate(tx.created_at)}</td>
            </tr>
          {/each}
          {#if txs.length === 0}<tr><td colspan="5" class="py-2 muted">No transactions.</td></tr
            >{/if}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card mt-4">
    <h2 class="hud font-display text-lg font-bold">Recent events</h2>
    <ul class="mt-2 space-y-1 text-xs font-mono">
      {#each events.slice(0, 15) as e}
        <li class="muted">[{e.block_number}] {e.name} · {shortHash(e.transaction_hash)}</li>
      {/each}
      {#if events.length === 0}<li class="muted">No events indexed.</li>{/if}
    </ul>
  </div>
</div>
