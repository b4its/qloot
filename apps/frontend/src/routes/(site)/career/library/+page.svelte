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
  // The student's top recommended major (from their analysis), if any.
  let topMajor: string | null = null;
  let recommendForMajor = false;
  $: totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedItems = paginate(items, currentPage, PAGE_SIZE);

  const tabs = [
    { key: "course", label: "Kursus", icon: "graduation-cap" },
    { key: "extracurricular", label: "Ekstrakurikuler", icon: "bolt" },
    { key: "material", label: "Materi", icon: "file-lines" },
  ];

  async function load() {
    loading = true;
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

  function search() {
    currentPage = 1;
    load();
  }

  async function pick(key: string) {
    category = key;
    currentPage = 1;
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

  <form class="mt-4 flex flex-wrap items-end gap-2" on:submit|preventDefault={search}>
    <label class="flex flex-1 flex-col text-xs">
      <span class="muted mb-1">Cari sumber daya</span>
      <input class="input" bind:value={query} placeholder="mis. matematika, olimpiade…" />
    </label>
    <button class="btn-primary !py-1.5" type="submit" disabled={loading}>Cari</button>
  </form>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  {#if loading}
    <Skeleton rows={4} />
  {:else if !items.length}
    <div class="card mt-4 text-center">
      <p class="muted">Belum ada sumber daya yang cocok.</p>
    </div>
  {:else}
    <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each pagedItems as item}
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
      total={items.length}
      {loading}
      label="sumber daya"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>
