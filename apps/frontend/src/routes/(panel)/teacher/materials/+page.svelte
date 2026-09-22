<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Material } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { formatDate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let file: File | null = null;
  let uploading = false;
  let loading = true;
  let materials: Material[] = [];
  let message = "";
  let error = "";
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    error = "";
    try {
      materials = await api.get<Material[]>(`/materials?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = materials.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat materi";
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

  async function upload(e: Event) {
    e.preventDefault();
    if (!file) return;
    error = "";
    message = "";
    uploading = true;
    try {
      const form = new FormData();
      form.append("file", file);
      const material = await api.post<Material>("/materials/upload", form);
      message = `Berhasil mengunggah ${material.filename}`;
      file = null;
      page = 1;
      await load();
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Upload gagal";
    } finally {
      uploading = false;
    }
  }

  async function removeMaterial(m: Material) {
    if (!confirm(`Hapus materi "${m.filename}"?`)) return;
    error = "";
    message = "";
    try {
      await api.delete(`/materials/${m.id}`);
      message = "Materi dihapus.";
      await load();
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal menghapus materi";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Materi — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Materi"
    title="Materi"
    subtitle="Unggah PDF pelajaran, lalu buka sebuah materi untuk membuat soal dengan AI dan bertanya."
    backHref="/teacher"
    backLabel="Panel Guru"
  />

  <PageAlerts {message} {error} />

  <form class="card mt-6" on:submit={upload}>
    <h2 class="hud font-display text-lg font-bold">Unggah PDF</h2>
    <input
      class="input mt-3"
      type="file"
      accept="application/pdf"
      on:change={(e) => (file = (e.currentTarget as HTMLInputElement).files?.[0] ?? null)}
    />
    <button class="btn-primary mt-3" type="submit" disabled={!file || uploading}>
      {#if uploading}<Icon name="spinner" spin size="12px" />{/if}
      {uploading ? "Mengunggah…" : "Unggah"}
    </button>
  </form>

  <div class="card mt-4">
    <h2 class="hud font-display text-lg font-bold">Materi saya</h2>
    {#if loading}
      <div class="mt-3 space-y-2">
        {#each Array(3) as _}<div class="skeleton h-10"></div>{/each}
      </div>
    {:else if materials.length === 0}
      <p class="mt-3 text-sm muted">Belum ada materi. Unggah PDF di atas untuk memulai.</p>
    {:else}
      <ul class="mt-2 space-y-2 text-sm">
        {#each materials as m}
          <li class="flex flex-wrap items-center justify-between gap-2 border-t pt-2">
            <span class="min-w-0">
              <span class="truncate font-medium">{m.filename}</span>
              <span class="block text-xs muted">{formatDate(m.created_at)} · {m.status}</span>
            </span>
            <span class="flex items-center gap-2">
              <a href={`/teacher/materials/${m.id}`} class="btn-ghost">
                <Icon name="wand-magic-sparkles" size="11px" /> AI & kelola
              </a>
              <button
                class="btn-icon !text-tertiary hover:!border-tertiary"
                on:click={() => removeMaterial(m)}
                aria-label="Hapus materi"
              >
                <Icon name="trash" size="12px" />
              </button>
            </span>
          </li>
        {/each}
      </ul>
    {/if}
    <Pagination
      {page}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="materi"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  </div>
</div>
