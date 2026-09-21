<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { BlockchainStatus, BlockchainTx } from "$lib/types";
  import { formatDate, shortHash, etherscanUrl, statusLabel } from "$lib/utils/format";

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
      message = `${action === "pause" ? "Jeda" : "Lanjutkan"} rewards diantrekan untuk blockchain worker`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim perintah";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Blockchain — QLoot</title></svelte:head>

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
        <div class="mono-label">Jaringan</div>
        <div class="font-semibold">{status.network}</div>
      </div>
      <div>
        <div class="mono-label">ID Chain</div>
        <div class="font-semibold">{status.chain_id}</div>
      </div>
      <div>
        <div class="mono-label">Mode</div>
        <div class="font-semibold">{status.dry_run ? "uji coba" : "langsung"}</div>
      </div>
      <div>
        <div class="mono-label">Konfirmasi</div>
        <div class="font-semibold">{status.confirmations_required}</div>
      </div>
      <div class="sm:col-span-2">
        <div class="mono-label">Kontrak</div>
        <div class="break-all font-mono text-xs">
          {status.contract_address ?? "belum diterapkan"}
        </div>
      </div>
      <div class="sm:col-span-2">
        <div class="mono-label">Treasury</div>
        <div class="break-all font-mono text-xs">{status.treasury_address ?? "belum diatur"}</div>
      </div>
    </div>

    <div class="mt-4 flex gap-2">
      <button class="btn-ghost" on:click={() => control("pause")}>Jeda hadiah</button>
      <button class="btn-primary" on:click={() => control("unpause")}>Lanjutkan hadiah</button>
    </div>
  {/if}

  <div class="card mt-4">
    <h2 class="hud font-display text-lg font-bold">Transaksi</h2>
    <div class="mt-2 overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">Metode</th><th>Status</th><th>Hash</th><th class="text-right">Konf</th
            ><th class="text-right">Waktu</th></tr
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
                  class:badge-amber={tx.status !== "confirmed"}>{statusLabel(tx.status)}</span
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
          {#if txs.length === 0}<tr><td colspan="5" class="py-2 muted">Belum ada transaksi.</td></tr
            >{/if}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card mt-4">
    <h2 class="hud font-display text-lg font-bold">Event terkini</h2>
    <ul class="mt-2 space-y-1 text-xs font-mono">
      {#each events.slice(0, 15) as e}
        <li class="muted">[{e.block_number}] {e.name} · {shortHash(e.transaction_hash)}</li>
      {/each}
      {#if events.length === 0}<li class="muted">Belum ada event terindeks.</li>{/if}
    </ul>
  </div>
</div>
