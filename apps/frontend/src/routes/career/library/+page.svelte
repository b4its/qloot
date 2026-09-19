<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { ResourceItem } from "$lib/types";

  let items: ResourceItem[] = [];
  let category = "course";
  let loading = true;
  let error = "";

  const tabs = [
    { key: "course", label: "Courses", icon: "🎓" },
    { key: "extracurricular", label: "Extracurriculars", icon: "⚡" },
    { key: "material", label: "Materials", icon: "📄" },
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

<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold">Resource Library</h1>
    <p class="mt-1 text-sm muted">
      Courses, extracurriculars and study materials (simulated catalog).
    </p>
  </div>
  <a href="/career" class="btn-ghost">← Career home</a>
</div>

<div class="mt-4 flex flex-wrap gap-1 border-b">
  {#each tabs as t}
    <button
      class="px-4 py-2 text-sm"
      class:border-b-2={category === t.key}
      class:border-primary-500={category === t.key}
      class:font-semibold={category === t.key}
      on:click={() => pick(t.key)}
    >
      {t.icon}
      {t.label}
    </button>
  {/each}
</div>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
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
      <div class="card">
        <div class="flex items-center justify-between">
          <span class="text-2xl" aria-hidden="true"
            >{category === "course" ? "🎓" : category === "extracurricular" ? "⚡" : "📄"}</span
          >
          <span
            class="badge"
            class:bg-green-100={item.is_free}
            class:text-green-700={item.is_free}
            class:bg-amber-100={!item.is_free}
            class:text-amber-700={!item.is_free}
          >
            {item.is_free ? "Free" : "Paid"}
          </span>
        </div>
        <h2 class="mt-2 font-semibold">{item.title}</h2>
        <p class="mt-1 text-sm muted">{item.description}</p>
        <div class="mt-2 flex items-center justify-between text-xs muted">
          <span>{item.provider ?? ""}</span>
          {#if item.tags?.length}<span>{item.tags.join(" · ")}</span>{/if}
        </div>
      </div>
    {/each}
  </div>
{/if}
