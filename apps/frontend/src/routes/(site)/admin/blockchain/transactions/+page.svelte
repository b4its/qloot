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

  async function load() {
    loading = true;
    error = "";
    try {
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

  onMount(load);
</script>

<svelte:head><title>Transaksi Blockchain — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Blockchain"
    title="Transaksi"
    subtitle="Semua transaksi on-chain OryphemCoin dan status konfirmasinya."
    backHref="/admin/blockchain"
    backLabel="Blockchain"
  />

  <PageAlerts {error} />

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
