<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { shortHash } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  interface BlockchainEventRow {
    name: string;
    transaction_hash: string;
    block_number: number;
    log_index?: number;
    args?: Record<string, unknown>;
  }

  const PAGE = 25;
  let events: BlockchainEventRow[] = [];
  let error = "";
  let loading = true;
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    error = "";
    try {
      events = await api.get<BlockchainEventRow[]>(
        `/blockchain/events?limit=${PAGE}&offset=${(page - 1) * PAGE}`,
      );
      hasMore = events.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat event";
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

<svelte:head><title>Event Blockchain — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Blockchain"
    title="Event"
    subtitle="Event kontrak yang terindeks dari transaksi on-chain."
    backHref="/admin/blockchain"
    backLabel="Blockchain"
  />

  <PageAlerts {error} />

  <div class="card mt-6">
    {#if loading}
      <div class="space-y-2">
        {#each Array(6) as _}<div class="skeleton h-6"></div>{/each}
      </div>
    {:else if events.length === 0}
      <p class="muted">Belum ada event terindeks.</p>
    {:else}
      <ul class="space-y-1 text-xs font-mono">
        {#each events as e}
          <li class="muted">[{e.block_number}] {e.name} · {shortHash(e.transaction_hash)}</li>
        {/each}
      </ul>
    {/if}
  </div>

  <Pagination
    {page}
    pageSize={PAGE}
    {hasMore}
    {loading}
    label="event"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>
