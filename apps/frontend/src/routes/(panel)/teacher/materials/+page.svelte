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
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import { reveal } from "$lib/actions/reveal";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let file: File | null = null;
  let dragging = false;
  let uploading = false;
  let loading = true;
  let materials: Material[] = [];
  let message = "";
  let error = "";
  let page = 1;
  let hasMore = false;
  let query = "";
  let statusFilter: "all" | "ready" | "uploaded" = "all";
  let qualityFilter: "all" | "ok" | "ocr" | "empty" = "all";

  // Human-readable file size.
  function humanSize(bytes: number): string {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
    return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  const qualityTone: Record<string, string> = {
    ok: "badge-mint",
    ocr: "badge-amber",
    empty: "badge-magenta",
  };
  const qualityLabel: Record<string, string> = {
    ok: "Teks siap",
    ocr: "Hasil OCR",
    empty: "Tanpa teks",
  };

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

  function pickFile(f: File | null) {
    file = f;
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragging = false;
    const dropped = e.dataTransfer?.files?.[0];
    if (dropped && dropped.type === "application/pdf") {
      pickFile(dropped);
    } else if (dropped) {
      error = "Hanya berkas PDF yang didukung.";
    }
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
    deletingMaterial = m;
  }

  async function confirmRemoveMaterial() {
    const m = deletingMaterial;
    if (!m) return;
    deletingMaterial = null;
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
  let deletingMaterial: Material | null = null;

  onMount(load);

  // --- derived metrics + filtering ------------------------------------------
  $: readyCount = materials.filter((m) => m.status === "ready").length;
  $: ocrCount = materials.filter((m) => m.extraction_status === "ocr").length;
  $: emptyCount = materials.filter((m) => m.extraction_status === "empty").length;
  $: totalSize = materials.reduce((s, m) => s + (m.size_bytes ?? 0), 0);

  $: filtered = materials.filter((m) => {
    if (statusFilter !== "all" && m.status !== statusFilter) return false;
    if (qualityFilter !== "all" && (m.extraction_status ?? "ok") !== qualityFilter) return false;
    if (query.trim() && !m.filename.toLowerCase().includes(query.toLowerCase().trim()))
      return false;
    return true;
  });
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

  <!-- Upload with drag & drop -->
  <form class="card mt-6" on:submit={upload}>
    <h2 class="hud font-display text-lg font-bold">Unggah PDF</h2>
    <label
      class="mt-3 grid place-items-center rounded-sm border-2 border-dashed px-4 py-8 text-center transition-colors cursor-pointer"
      class:border-primary={dragging}
      class:surface={dragging}
      on:dragover|preventDefault={() => (dragging = true)}
      on:dragleave={() => (dragging = false)}
      on:drop={onDrop}
    >
      <input
        class="sr-only"
        type="file"
        accept="application/pdf"
        on:change={(e) => pickFile((e.currentTarget as HTMLInputElement).files?.[0] ?? null)}
        aria-label="Pilih berkas PDF"
      />
      <Icon name="cloud-arrow-up" size="26px" class="muted" />
      <p class="mt-2 text-sm">
        {#if file}
          <span class="font-medium">{file.name}</span>
          <span class="muted"> · {humanSize(file.size)}</span>
        {:else}
          <span class="font-medium">Tarik PDF ke sini</span>
          <span class="muted"> atau klik untuk memilih</span>
        {/if}
      </p>
      <p class="mt-1 text-xs muted">Hanya berkas PDF.</p>
    </label>
    <div class="mt-3 flex items-center gap-2">
      <button class="btn-primary" type="submit" disabled={!file || uploading}>
        {#if uploading}<Icon name="spinner" spin size="12px" />{:else}<Icon
            name="upload"
            size="12px"
          />{/if}
        {uploading ? "Mengunggah…" : "Unggah"}
      </button>
      {#if file}
        <button type="button" class="btn-ghost" on:click={() => pickFile(null)}>Batal</button>
      {/if}
    </div>
  </form>

  <div class="card mt-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 class="hud font-display text-lg font-bold">Materi saya</h2>
      {#if !loading && materials.length}
        <span class="mono-label">{materials.length} materi · {humanSize(totalSize)}</span>
      {/if}
    </div>

    {#if loading}
      <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {#each Array(4) as _}<div class="skeleton h-20"></div>{/each}
      </div>
      <div class="mt-3 space-y-2">
        {#each Array(3) as _}<div class="skeleton h-10"></div>{/each}
      </div>
    {:else if materials.length === 0}
      <p class="mt-3 text-sm muted">Belum ada materi. Unggah PDF di atas untuk memulai.</p>
    {:else}
      <!-- Metrics -->
      <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="card p-4">
          <p class="mono-label text-[10px]">Total</p>
          <p class="mt-1 font-display text-2xl font-bold">{materials.length}</p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Siap soal AI</p>
          <p class="mt-1 font-display text-2xl font-bold text-mint" data-role="ready-count">
            {readyCount}
          </p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Hasil OCR</p>
          <p class="mt-1 font-display text-2xl font-bold text-highlight">{ocrCount}</p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Tanpa teks</p>
          <p class="mt-1 font-display text-2xl font-bold">{emptyCount}</p>
        </div>
      </div>

      <!-- Search + filters -->
      <div class="mt-4 flex flex-wrap items-center gap-2">
        <div class="relative flex-1 min-w-[180px]">
          <Icon
            name="magnifying-glass"
            size="12px"
            class="absolute left-3 top-1/2 -translate-y-1/2 muted"
          />
          <input
            class="input text-xs !py-1.5 !pl-8 w-full"
            placeholder="Cari materi..."
            bind:value={query}
            aria-label="Cari materi"
          />
        </div>
        <select
          class="input text-xs !py-1.5 w-auto"
          bind:value={statusFilter}
          aria-label="Filter status"
        >
          <option value="all">Semua status</option>
          <option value="ready">Siap</option>
          <option value="uploaded">Terunggah</option>
        </select>
        <select
          class="input text-xs !py-1.5 w-auto"
          bind:value={qualityFilter}
          aria-label="Filter kualitas"
        >
          <option value="all">Semua kualitas</option>
          <option value="ok">Teks siap</option>
          <option value="ocr">Hasil OCR</option>
          <option value="empty">Tanpa teks</option>
        </select>
      </div>

      {#if filtered.length === 0}
        <p class="mt-4 text-center text-xs muted">Tidak ada materi yang cocok dengan filtermu.</p>
      {:else}
        <ul class="mt-3 space-y-2 text-sm">
          {#each filtered as m, i (m.id)}
            {@const quality = m.extraction_status ?? "ok"}
            <li
              use:reveal={{ delay: i * 15 }}
              class="flex flex-wrap items-center justify-between gap-2 border-t pt-3"
              data-material={m.id}
            >
              <span class="flex min-w-0 items-center gap-3">
                <span class="tile-neutral h-9 w-9 flex-none">
                  <Icon name="file-pdf" size="14px" class="text-tertiary" />
                </span>
                <span class="min-w-0">
                  <span class="truncate font-medium">{m.filename}</span>
                  <span class="mono-label mt-0.5 flex flex-wrap items-center gap-2">
                    <span class="badge {qualityTone[quality] ?? 'badge-neutral'}">
                      {qualityLabel[quality] ?? quality}
                    </span>
                    <span>{humanSize(m.size_bytes)}</span>
                    <span>·</span>
                    <span>{formatDate(m.created_at)}</span>
                  </span>
                </span>
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

{#if deletingMaterial}
  <ConfirmDialog
    title="Hapus Materi"
    description={`Materi "${deletingMaterial.filename}" beserta hasil ekstraksinya akan dihapus.`}
    confirmLabel="Ya, Hapus"
    onConfirm={confirmRemoveMaterial}
    close={() => (deletingMaterial = null)}
  />
{/if}
