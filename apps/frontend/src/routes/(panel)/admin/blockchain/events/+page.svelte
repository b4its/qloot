<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatNumber, shortHash } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Icon from "$lib/components/Icon.svelte";

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
  let nameFilter = "";
  let query = "";
  let expanded = new Set<string>();

  async function load() {
    if (!hasRole($auth.user, "admin")) return;
    loading = true;
    error = "";
    try {
      const qs = new URLSearchParams({
        limit: String(PAGE),
        offset: String((page - 1) * PAGE),
      });
      if (nameFilter) qs.set("name", nameFilter);
      events = await api.get<BlockchainEventRow[]>(`/blockchain/events?${qs.toString()}`);
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

  function applyName(name: string) {
    nameFilter = name;
    page = 1;
    load();
  }

  function toggle(id: string) {
    if (expanded.has(id)) expanded.delete(id);
    else expanded.add(id);
    expanded = new Set(expanded);
  }

  function rowId(e: BlockchainEventRow): string {
    return `${e.transaction_hash}:${e.log_index ?? 0}`;
  }

  onMount(load);

  // --- metrics + client-side search ------------------------------------------
  $: nameCounts = events.reduce<Record<string, number>>((acc, e) => {
    acc[e.name] = (acc[e.name] ?? 0) + 1;
    return acc;
  }, {});
  $: topNames = Object.entries(nameCounts).sort((a, b) => b[1] - a[1]);
  $: latestBlock = events.length ? Math.max(...events.map((e) => e.block_number)) : null;

  $: filtered = events.filter((e) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase().trim();
    return (
      e.name.toLowerCase().includes(q) ||
      e.transaction_hash.toLowerCase().includes(q) ||
      String(e.block_number).includes(q)
    );
  });
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

  <!-- Metrics -->
  {#if !loading && events.length > 0}
    <div class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Event (halaman ini)</p>
        <p class="mt-1 font-display text-3xl font-bold" data-role="event-count">{events.length}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Jenis event</p>
        <p class="mt-1 font-display text-3xl font-bold text-primary" data-role="name-count">
          {topNames.length}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Blok terbaru</p>
        <p class="mt-1 font-display text-3xl font-bold">{latestBlock ?? "—"}</p>
      </div>
    </div>
  {/if}

  <!-- Name filter chips + search -->
  {#if !loading && events.length > 0}
    <div class="mt-4 flex flex-wrap items-center gap-2">
      <div class="flex flex-wrap gap-1">
        <button
          type="button"
          class="badge"
          class:badge-mint={nameFilter === ""}
          class:badge-neutral={nameFilter !== ""}
          on:click={() => applyName("")}>Semua</button
        >
        {#each topNames as [name, count]}
          <button
            type="button"
            class="badge"
            class:badge-mint={nameFilter === name}
            class:badge-neutral={nameFilter !== name}
            on:click={() => applyName(name)}
          >
            {name} ({count})
          </button>
        {/each}
      </div>
      <div class="relative ml-auto w-full sm:w-64">
        <Icon
          name="magnifying-glass"
          size="12px"
          class="absolute left-3 top-1/2 -translate-y-1/2 muted"
        />
        <input
          class="input text-xs !py-1.5 !pl-8 w-full"
          placeholder="Cari event, hash, atau blok..."
          bind:value={query}
          aria-label="Cari event"
        />
      </div>
    </div>
  {/if}

  <div class="card mt-4">
    {#if loading}
      <div class="space-y-2">
        {#each Array(6) as _}<div class="skeleton h-6"></div>{/each}
      </div>
    {:else if events.length === 0}
      <p class="muted">Belum ada event terindeks.</p>
    {:else if filtered.length === 0}
      <p class="muted">Tidak ada event yang cocok dengan pencarianmu.</p>
    {:else}
      <ul class="divide-y text-xs">
        {#each filtered as e (rowId(e))}
          <li class="py-2">
            <button
              type="button"
              class="flex w-full flex-wrap items-center gap-2 text-left"
              on:click={() => toggle(rowId(e))}
              aria-expanded={expanded.has(rowId(e))}
            >
              <span class="badge badge-indigo">{e.name}</span>
              <span class="muted">blok {formatNumber(e.block_number)}</span>
              <span class="font-mono muted">{shortHash(e.transaction_hash)}</span>
              {#if e.args && Object.keys(e.args).length}
                <Icon
                  name={expanded.has(rowId(e)) ? "chevron-down" : "chevron-right"}
                  size="10px"
                  class="ml-auto muted"
                />
              {/if}
            </button>
            {#if expanded.has(rowId(e)) && e.args}
              <dl
                class="mt-2 grid gap-x-6 gap-y-1 rounded-sm border p-3 text-[11px] sm:grid-cols-2"
              >
                {#each Object.entries(e.args) as [k, v]}
                  <div class="flex justify-between gap-2">
                    <dt class="muted">{k}</dt>
                    <dd class="font-mono text-right break-all">{String(v)}</dd>
                  </div>
                {/each}
              </dl>
            {/if}
          </li>
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
