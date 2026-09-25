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

  // Tx detail (gas + events) opened from a row.
  interface TxDetail {
    method: string;
    status: string;
    gas_limit?: number | null;
    gas_used?: number | null;
    effective_gas_price?: number | null;
    arguments_hash?: string | null;
    error_message?: string | null;
    explorer_url?: string | null;
    events?: { name: string; args: Record<string, unknown> | null }[];
  }
  let detailHash = "";
  let detail: TxDetail | null = null;
  let detailLoading = false;

  async function openDetail(tx: BlockchainTx) {
    if (!tx.transaction_hash) return;
    detailHash = tx.transaction_hash;
    detail = null;
    detailLoading = true;
    try {
      detail = await api.get<TxDetail>(`/blockchain/transactions/${tx.transaction_hash}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat detail transaksi";
    } finally {
      detailLoading = false;
    }
  }

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
                <td class="px-5 py-3"
                  ><span class="badge badge-magenta">{f.error_code ?? "failed"}</span></td
                >
                <td
                  class="px-5 py-3 max-w-[280px] truncate text-xs muted"
                  title={f.error_message ?? ""}>{f.error_message ?? "—"}</td
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
              ><th class="px-5 py-3">Metode</th><th class="px-5 py-3">Status</th><th
                class="px-5 py-3">Hash</th
              ><th class="px-5 py-3 text-right">Konf</th><th class="px-5 py-3 text-right">Waktu</th
              ><th class="px-5 py-3"></th></tr
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
                <td class="px-5 py-3 text-right">
                  <button
                    class="btn-ghost !py-1 text-xs"
                    on:click={() => openDetail(tx)}
                    disabled={!tx.transaction_hash}>Detail</button
                  >
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>

    {#if detailHash}
      <div class="card mt-4">
        <div class="flex items-center justify-between">
          <p class="mono-label">Detail transaksi {shortHash(detailHash)}</p>
          <button class="btn-ghost !py-1 text-xs" on:click={() => (detailHash = "")}>Tutup</button>
        </div>
        {#if detailLoading}
          <p class="mt-2 muted text-sm">Memuat…</p>
        {:else if detail}
          <dl class="mt-3 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            <div class="flex justify-between border-b py-1">
              <dt class="muted">Gas limit</dt>
              <dd>{detail.gas_limit ?? "—"}</dd>
            </div>
            <div class="flex justify-between border-b py-1">
              <dt class="muted">Gas terpakai</dt>
              <dd>{detail.gas_used ?? "—"}</dd>
            </div>
            <div class="flex justify-between border-b py-1">
              <dt class="muted">Harga gas efektif</dt>
              <dd>{detail.effective_gas_price ?? "—"}</dd>
            </div>
            <div class="flex justify-between border-b py-1">
              <dt class="muted">Hash argumen</dt>
              <dd class="font-mono text-xs">{detail.arguments_hash?.slice(0, 18) ?? "—"}…</dd>
            </div>
          </dl>
          {#if detail.error_message}
            <p class="alert-error mt-2 text-xs">{detail.error_message}</p>
          {/if}
          {#if detail.events && detail.events.length}
            <p class="mono-label mt-3">Event</p>
            <ul class="mt-1 space-y-1 text-xs">
              {#each detail.events as ev}
                <li class="font-mono">{ev.name}</li>
              {/each}
            </ul>
          {/if}
        {/if}
      </div>
    {/if}
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
