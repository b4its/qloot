<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { ResourceItem } from "$lib/types";

  let items: ResourceItem[] = [];
  let category = "course";
  let loading = true;
  let error = "";

  const tabs = [
    { key: "course", label: "Kursus", icon: "graduation-cap" },
    { key: "extracurricular", label: "Ekstrakurikuler", icon: "bolt" },
    { key: "material", label: "Materi", icon: "file-lines" },
  ];

  async function load() {
    loading = true;
    try {
      items = await api.get<ResourceItem[]>(`/career/resources?category=${category}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load resources";
    } finally {
      loading = false;
    }
  }

  async function pick(key: string) {
    category = key;
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>Resource Library — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Resource</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Resource Library</h1>
      <p class="mt-1 text-sm muted">
        Kursus, ekstrakurikuler, dan materi belajar (katalog simulasi).
      </p>
    </div>
    <a href="/career" class="btn-ghost">← Career home</a>
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

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  {#if loading}
    <p class="mt-6 muted">Loading…</p>
  {:else if !items.length}
    <div class="card mt-4 text-center"><p class="muted">No resources in this category.</p></div>
  {:else}
    <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each items as item}
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
              {item.is_free ? "Free" : "Paid"}
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
  {/if}
</div>
