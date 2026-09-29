<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { ResourceItem, Recommendation } from "$lib/types";
  import Pagination from "$lib/components/Pagination.svelte";
  import { paginate } from "$lib/utils/format";

  const PAGE_SIZE = 12;
  let items: ResourceItem[] = [];
  let category = "course";
  let loading = true;
  let error = "";
  let currentPage = 1;
  // CARE-07: free-text search over the catalog.
  let query = "";
  // Local view filters (applied client-side over the fetched page set).
  let costFilter: "all" | "free" | "paid" = "all";
  let providerFilter = "all";
  let sortBy: "title" | "provider" = "title";
  // The student's top recommended major (from their analysis), if any.
  let topMajor: string | null = null;
  let recommendForMajor = false;

  // --- derived metrics + filters ---------------------------------------------
  $: freeCount = items.filter((i) => i.is_free).length;
  $: paidCount = items.length - freeCount;
  $: providers = [...new Set(items.map((i) => i.provider).filter(Boolean))] as string[];

  $: filtered = items
    .filter((i) => {
      if (costFilter === "free" && !i.is_free) return false;
      if (costFilter === "paid" && i.is_free) return false;
      if (providerFilter !== "all" && i.provider !== providerFilter) return false;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "provider") return (a.provider ?? "").localeCompare(b.provider ?? "");
      return a.title.localeCompare(b.title);
    });

  $: totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedItems = paginate(filtered, currentPage, PAGE_SIZE);

  const tabs = [
    { key: "course", label: "Kursus", icon: "graduation-cap" },
    { key: "extracurricular", label: "Ekstrakurikuler", icon: "bolt" },
    { key: "material", label: "Materi", icon: "file-lines" },
  ];

  async function load() {
    loading = true;
    error = "";
    try {
      const qs = new URLSearchParams({ category, limit: "200" });
      if (query.trim()) qs.set("q", query.trim());
      if (recommendForMajor && topMajor) qs.set("major", topMajor);
      items = await api.get<ResourceItem[]>(`/career/resources?${qs.toString()}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat sumber daya";
    } finally {
      loading = false;
    }
  }

  // Debounced server-side search so typing feels instant without hammering the API.
  let debounce: ReturnType<typeof setTimeout> | null = null;
  function onSearch() {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => {
      currentPage = 1;
      void load();
    }, 250);
  }

  function resetFilters() {
    query = "";
    costFilter = "all";
    providerFilter = "all";
    sortBy = "title";
    currentPage = 1;
    void load();
  }

  async function pick(key: string) {
    category = key;
    currentPage = 1;
    costFilter = "all";
    providerFilter = "all";
    await load();
  }

  async function toggleMajor() {
    recommendForMajor = !recommendForMajor;
    currentPage = 1;
    await load();
  }

  onMount(async () => {
    try {
      const recs = await api.get<Recommendation[]>("/career/recommendations");
      if (recs.length) topMajor = recs[0].major;
    } catch {
      /* recommendations are optional */
    }
    await load();
  });
</script>

<svelte:head><title>Perpustakaan Sumber Daya — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Sumber Daya</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Perpustakaan Sumber Daya</h1>
      <p class="mt-1 text-sm muted">
        Kursus, ekstrakurikuler, dan materi belajar (katalog simulasi).
      </p>
    </div>
    <a href="/career" class="btn-ghost">← Beranda karier</a>
  </div>

  <div class="mt-6 flex flex-wrap gap-1 border-b">
    {#each tabs as t}
      <button
        class="hud px-4 py-2 text-xs transition-colors"
        class:text-primary={category === t.key}
        class:border-b-2={category === t.key}
        class:border-primary={category === t.key}
        on:click={() => pick(t.key)}
      >
        <Icon name={t.icon} size="12px" />
        {t.label}
      </button>
    {/each}
  </div>

  {#if topMajor}
    <div class="mt-4">
      <button
        type="button"
        class="btn-pill transition-colors"
        class:!border-primary={recommendForMajor}
        class:!text-primary={recommendForMajor}
        aria-pressed={recommendForMajor}
        on:click={toggleMajor}
      >
        <Icon name="star" size="11px" />
        Disarankan untuk {topMajor}
      </button>
    </div>
  {/if}

  <!-- Metrics -->
  {#if !loading && items.length > 0}
    <div class="mt-6 grid grid-cols-3 gap-3">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total</p>
        <p class="mt-1 font-display text-3xl font-bold" data-role="total-count">{items.length}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Gratis</p>
        <p class="mt-1 font-display text-3xl font-bold text-mint" data-role="free-count">
          {freeCount}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Berbayar</p>
        <p class="mt-1 font-display text-3xl font-bold text-highlight">{paidCount}</p>
      </div>
    </div>
  {/if}

  <!-- Search + filters -->
  <div class="mt-4 flex flex-wrap items-center gap-2">
    <div class="relative flex-1 min-w-[200px]">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        bind:value={query}
        on:input={onSearch}
        placeholder="Cari sumber daya…"
        aria-label="Cari sumber daya"
      />
    </div>
    <div class="flex items-center gap-1 rounded-sm border p-1 surface text-xs">
      {#each [["all", "Semua"], ["free", "Gratis"], ["paid", "Berbayar"]] as [val, label]}
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={costFilter === val}
          class:text-[#05060A]={costFilter === val}
          class:muted={costFilter !== val}
          aria-pressed={costFilter === val}
          on:click={() => {
            costFilter = val as typeof costFilter;
            currentPage = 1;
          }}
        >
          {label}
        </button>
      {/each}
    </div>
    {#if providers.length > 1}
      <select
        class="input text-xs !py-1.5 w-auto"
        bind:value={providerFilter}
        on:change={() => (currentPage = 1)}
        aria-label="Filter penyedia"
      >
        <option value="all">Semua penyedia</option>
        {#each providers as p}<option value={p}>{p}</option>{/each}
      </select>
    {/if}
    <select
      class="input text-xs !py-1.5 w-auto"
      bind:value={sortBy}
      on:change={() => (currentPage = 1)}
      aria-label="Urutkan"
    >
      <option value="title">Judul (A–Z)</option>
      <option value="provider">Penyedia</option>
    </select>
  </div>

  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">
      {error}
    </p>
  {/if}

  {#if loading}
    <Skeleton rows={4} />
  {:else if !items.length}
    <div class="card mt-4 text-center space-y-3">
      <p class="muted">Belum ada sumber daya yang cocok dengan pencarianmu.</p>
      <button class="btn-ghost" on:click={resetFilters}>Reset Filter</button>
    </div>
  {:else if !filtered.length}
    <div class="card mt-4 text-center space-y-3">
      <p class="muted">Tidak ada sumber daya yang cocok dengan filtermu.</p>
      <button class="btn-ghost" on:click={resetFilters}>Reset Filter</button>
    </div>
  {:else}
    <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each pagedItems as item (item.code)}
        <div class="card lift">
          <div class="flex items-center justify-between">
            <span class="tile h-10 w-10" aria-hidden="true"
              ><Icon
                name={category === "course"
                  ? "graduation-cap"
                  : category === "extracurricular"
                    ? "bolt"
                    : "file-lines"}
                size="18px"
              /></span
            >
            <span class="badge" class:badge-mint={item.is_free} class:badge-amber={!item.is_free}>
              {item.is_free ? "Gratis" : "Berbayar"}
            </span>
          </div>
          <h2 class="mt-3 font-display text-base font-bold">{item.title}</h2>
          <p class="mt-1 text-sm muted">{item.description}</p>
          <div class="mt-2 flex items-center justify-between text-xs muted">
            <span>{item.provider ?? ""}</span>
            {#if item.tags?.length}<span>{item.tags.join(" · ")}</span>{/if}
          </div>
        </div>
      {/each}
    </div>
    <Pagination
      page={currentPage}
      pageSize={PAGE_SIZE}
      total={filtered.length}
      {loading}
      label="sumber daya"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>
