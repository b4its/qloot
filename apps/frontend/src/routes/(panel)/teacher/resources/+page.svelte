<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { ResourceItem } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Icon from "$lib/components/Icon.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let items: ResourceItem[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let category = "";
  let query = "";
  let busy = false;
  let form = { code: "", category: "course", title: "", description: "", provider: "" };

  async function load() {
    loading = true;
    error = "";
    try {
      const qs = new URLSearchParams({ limit: "200" });
      if (category) qs.set("category", category);
      if (query.trim()) qs.set("q", query.trim());
      items = await api.get<ResourceItem[]>(`/career/resources?${qs.toString()}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat sumber daya";
    } finally {
      loading = false;
    }
  }

  async function createResource() {
    busy = true;
    message = "";
    error = "";
    try {
      await api.post("/career/resources", {
        ...form,
        is_free: true,
        tags: [],
      });
      message = `Sumber daya "${form.title}" ditambahkan.`;
      form = { code: "", category: "course", title: "", description: "", provider: "" };
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menambah sumber daya";
    } finally {
      busy = false;
    }
  }

  async function removeResource(item: ResourceItem) {
    if (!confirm(`Hapus "${item.title}"?`)) return;
    try {
      await api.delete(`/career/resources/${item.code}`);
      message = "Sumber daya dihapus.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus sumber daya";
    }
  }

  function search() {
    load();
  }

  onMount(load);
</script>

<svelte:head><title>Sumber Daya — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-6xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Sumber Daya"
    title="Perpustakaan Sumber Daya"
    subtitle="Kelola katalog kursus, ekstrakurikuler, dan materi belajar."
    backHref="/teacher"
    backLabel="Panel guru"
  />

  <PageAlerts {message} {error} />

  <form class="mt-6 flex flex-wrap items-end gap-2" on:submit|preventDefault={search}>
    <label class="flex flex-col text-xs">
      <span class="muted mb-1">Kategori</span>
      <select class="input !w-auto" bind:value={category} on:change={load}>
        <option value="">Semua</option>
        <option value="course">Kursus</option>
        <option value="extracurricular">Ekstrakurikuler</option>
        <option value="material">Materi</option>
      </select>
    </label>
    <label class="flex flex-1 flex-col text-xs">
      <span class="muted mb-1">Cari</span>
      <input class="input" bind:value={query} placeholder="judul atau deskripsi…" />
    </label>
    <button class="btn-ghost !py-1.5" type="submit" disabled={loading}>Cari</button>
  </form>

  <div class="card mt-6">
    <h2 class="font-display font-bold">Tambah sumber daya</h2>
    <div class="mt-3 grid gap-2 sm:grid-cols-2">
      <input class="input" placeholder="Kode (unik)" bind:value={form.code} />
      <select class="input" bind:value={form.category}>
        <option value="course">Kursus</option>
        <option value="extracurricular">Ekstrakurikuler</option>
        <option value="material">Materi</option>
      </select>
      <input class="input sm:col-span-2" placeholder="Judul" bind:value={form.title} />
      <input class="input" placeholder="Penyedia (opsional)" bind:value={form.provider} />
      <input class="input" placeholder="Deskripsi (opsional)" bind:value={form.description} />
    </div>
    <button
      class="btn-primary mt-3 !py-1.5"
      on:click={createResource}
      disabled={busy || form.code.length < 2 || form.title.length < 2}>Tambah</button
    >
  </div>

  <div class="card mt-4 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(5) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if items.length === 0}
      <p class="muted">Belum ada sumber daya.</p>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr><th class="py-1">Kode</th><th>Kategori</th><th>Judul</th><th></th></tr>
        </thead>
        <tbody>
          {#each items as r (r.code)}
            <tr class="border-t">
              <td class="py-1 font-mono text-xs">{r.code}</td>
              <td>{r.category}</td>
              <td>{r.title}</td>
              <td class="text-right">
                <button
                  class="btn-icon !text-tertiary"
                  aria-label="Hapus sumber daya"
                  on:click={() => removeResource(r)}
                >
                  <Icon name="trash" size="12px" />
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>
