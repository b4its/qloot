<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { BlockchainTx } from "$lib/types";
  import { formatDate, shortHash, etherscanUrl, statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  const PAGE = 25;
  let txs: BlockchainTx[] = [];
  let chainId: number | undefined = undefined;
  let error = "";
  let loading = true;
  let page = 1;
  let hasMore = false;
  let failedOnly = false;

  interface FailedTx {
    id: string;
    method: string;
    status: string;
    error_code?: string | null;
    error_message?: string | null;
    transaction_hash?: string | null;
    allocation_id?: string | null;
    withdrawal_id?: string | null;
  }
  let failed: FailedTx[] = [];

  async function load() {
    loading = true;
    error = "";
    try {
      if (failedOnly) {
        failed = await api.get<FailedTx[]>(
          `/blockchain/transactions/failed?limit=${PAGE}&offset=${(page - 1) * PAGE}`,
        );
        hasMore = failed.length === PAGE;
      } else {
        [txs, chainId] = await Promise.all([
          api.get<BlockchainTx[]>(
            `/blockchain/transactions?limit=${PAGE}&offset=${(page - 1) * PAGE}`,
          ),
          api
            .get<{ chain_id: number }>("/blockchain/status/admin")
            .then((s) => s.chain_id)
            .catch(() => undefined as number | undefined),
        ]);
        hasMore = txs.length === PAGE;
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat transaksi";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    page = next;
    load();
  }

  function toggleFailed() {
    failedOnly = !failedOnly;
    page = 1;
    load();
  }

  onMount(load);
</script>

<svelte:head><title>Transaksi Blockchain — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Blockchain"
    title="Transaksi"
    subtitle="Semua transaksi on-chain aset QLoot (OPT/QTC/ORT + ORX) dan status konfirmasinya."
    backHref="/admin/blockchain"
    backLabel="Blockchain"
  />

  <PageAlerts {error} />

  <div class="mt-4 flex items-center gap-2">
    <button class="btn-ghost" on:click={toggleFailed}>
      {failedOnly ? "← Semua transaksi" : "Hanya yang gagal"}
    </button>
  </div>

  {#if failedOnly}
    <div class="card mt-4 overflow-x-auto !p-0">
      {#if loading}
        <div class="space-y-2 p-5">
          {#each Array(6) as _}<div class="skeleton h-8"></div>{/each}
        </div>
      {:else if failed.length === 0}
        <p class="p-5 muted">Tidak ada transaksi gagal.</p>
      {:else}
        <table class="w-full text-sm">
          <thead class="mono-label border-b text-left">
            <tr
              ><th class="px-5 py-3">Metode</th><th class="px-5 py-3">Kode</th><th class="px-5 py-3"
                >Pesan</th
              ><th class="px-5 py-3">Sumber</th></tr
            >
          </thead>
          <tbody>
            {#each failed as f}
              <tr class="border-b last:border-0">
                <td class="px-5 py-3">{f.method}</td>
                <td class="px-5 py-3"><span class="badge badge-magenta">{f.error_code ?? "failed"}</span></td>
                <td class="px-5 py-3 max-w-[280px] truncate text-xs muted" title={f.error_message ?? ""}
                  >{f.error_message ?? "—"}</td
                >
                <td class="px-5 py-3 font-mono text-xs">
                  {#if f.allocation_id}alokasi {(f.allocation_id ?? "").slice(0, 8)}…
                  {:else if f.withdrawal_id}penarikan {(f.withdrawal_id ?? "").slice(0, 8)}…
                  {:else}—{/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  {:else}

  <div class="card mt-6 overflow-x-auto !p-0">
    {#if loading}
      <div class="space-y-2 p-5">
        {#each Array(6) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if txs.length === 0}
      <p class="p-5 muted">Belum ada transaksi.</p>
    {:else}
      <table class="w-full text-sm">
        <thead class="mono-label border-b text-left">
          <tr
            ><th class="px-5 py-3">Metode</th><th class="px-5 py-3">Status</th><th class="px-5 py-3"
              >Hash</th
            ><th class="px-5 py-3 text-right">Konf</th><th class="px-5 py-3 text-right">Waktu</th
            ></tr
          >
        </thead>
        <tbody>
          {#each txs as tx}
            {@const url = tx.explorer_url ?? etherscanUrl(tx.transaction_hash, chainId)}
            <tr class="border-b last:border-0">
              <td class="px-5 py-3">{tx.method}</td>
              <td class="px-5 py-3">
                <span
                  class="badge"
                  class:badge-mint={tx.status === "confirmed"}
                  class:badge-amber={tx.status !== "confirmed"}>{statusLabel(tx.status)}</span
                >
              </td>
              <td class="px-5 py-3 font-mono text-xs">
                {#if url}<a
                    class="text-primary"
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer">{shortHash(tx.transaction_hash)} ↗</a
                  >
                {:else}{shortHash(tx.transaction_hash)}{/if}
              </td>
              <td class="px-5 py-3 text-right">{tx.confirmation_count}</td>
              <td class="px-5 py-3 text-right text-xs muted">{formatDate(tx.created_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
  {/if}

  <Pagination
    {page}
    pageSize={PAGE}
    {hasMore}
    {loading}
    label="transaksi"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>
