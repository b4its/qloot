<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Material, Question } from "$lib/types";
  import { formatDate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";

  interface Summary {
    summary: string;
    key_points: string[];
  }
  interface Answer {
    answer: string;
    confidence_bp: number;
  }

  let file: File | null = null;
  let uploading = false;
  let loading = true;
  let materials: Material[] = [];
  let message = "";
  let error = "";
  let generated: Question[] = [];
  let count = 3;
  let selected: Material | null = null;

  // AI study assistant state (per selected material).
  let summary: Summary | null = null;
  let summaryLoading = false;
  let question = "";
  let asking = false;
  let asks: { q: string; a: Answer }[] = [];

  async function loadMaterials() {
    loading = true;
    try {
      materials = await api.get<Material[]>("/materials");
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal memuat materi";
    } finally {
      loading = false;
    }
  }

  function resetAssistant() {
    summary = null;
    asks = [];
    question = "";
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
      materials = [material, ...materials];
      file = null;
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Upload gagal";
    } finally {
      uploading = false;
    }
  }

  async function generate(m: Material) {
    selected = m;
    generated = [];
    error = "";
    message = "";
    resetAssistant();
    try {
      generated = await api.post<Question[]>(`/materials/${m.id}/generate-questions-sync`, {
        count,
        language: "id",
      });
      message = `Membuat ${generated.length} draf soal — tinjau sebelum dipublikasikan.`;
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal membuat soal";
    }
  }

  async function approve(q: Question) {
    try {
      await api.patch(`/questions/${q.id}`, { review_status: "approved" });
      generated = generated.map((g) => (g.id === q.id ? { ...g, review_status: "approved" } : g));
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal menyetujui";
    }
  }

  async function loadSummary() {
    if (!selected) return;
    summaryLoading = true;
    summary = null;
    try {
      summary = await api.get<Summary>(`/materials/${selected.id}/summary`);
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal merangkum materi";
    } finally {
      summaryLoading = false;
    }
  }

  async function ask() {
    if (!selected || question.trim().length < 3) return;
    const q = question.trim();
    asking = true;
    try {
      const a = await api.post<Answer>(`/materials/${selected.id}/ask`, { question: q });
      asks = [{ q, a }, ...asks];
      question = "";
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal menanyakan materi";
    } finally {
      asking = false;
    }
  }

  onMount(loadMaterials);
</script>

<svelte:head><title>Materi — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <p class="mono-label">Panel Guru · Materi</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Materi</h1>
  <p class="mt-1 muted">
    Unggah PDF, susun soal esai dengan AI, dan gunakan asisten materi untuk merangkum & bertanya.
  </p>

  {#if message}<p class="alert-ok mt-4">
      {message}
    </p>{/if}
  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

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
          <li
            class="flex flex-wrap items-center justify-between gap-2 border-t pt-2"
            class:row-me={selected?.id === m.id}
          >
            <span class="min-w-0">
              <span class="truncate font-medium">{m.filename}</span>
              <span class="block text-xs muted">
                {formatDate(m.created_at)} · {m.status}
              </span>
            </span>
            <span class="flex items-center gap-2">
              <input class="input w-16 !py-1" type="number" min="1" max="20" bind:value={count} />
              <button class="btn-ghost" on:click={() => generate(m)}>Buat soal</button>
              <button
                class="btn-ghost"
                on:click={() => {
                  selected = m;
                  resetAssistant();
                }}
                disabled={selected?.id === m.id}>Asisten</button
              >
            </span>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  {#if selected}
    <div class="card mt-4">
      <div class="flex items-center justify-between">
        <h2 class="hud font-display text-lg font-bold">Asisten materi</h2>
        <span class="badge badge-indigo truncate">{selected.filename}</span>
      </div>
      <p class="mt-1 text-xs muted">Ringkasan AI dan tanya-jawab yang terikat pada materi ini.</p>

      <div class="mt-3 flex flex-wrap gap-2">
        <button class="btn-secondary" on:click={loadSummary} disabled={summaryLoading}>
          {#if summaryLoading}<Icon name="spinner" spin size="12px" />{:else}<Icon
              name="wand-magic-sparkles"
              size="12px"
            />{/if}
          Ringkas materi
        </button>
      </div>

      {#if summary}
        <div class="alert-info mt-3">
          <span>
            <strong>Ringkasan:</strong>
            {summary.summary}
          </span>
        </div>
        {#if summary.key_points?.length}
          <ul class="mt-2 space-y-1 text-sm">
            {#each summary.key_points as kp}
              <li class="flex items-start gap-2">
                <Icon name="circle-check" class="mt-0.5 text-secondary" size="11px" />
                {kp}
              </li>
            {/each}
          </ul>
        {/if}
      {/if}

      <div class="mt-4 flex items-center gap-2">
        <input
          class="input"
          placeholder="Tanyakan sesuatu tentang materi ini…"
          bind:value={question}
          on:keydown={(e) => e.key === "Enter" && ask()}
        />
        <button
          class="btn-primary flex-none"
          on:click={ask}
          disabled={asking || question.trim().length < 3}
        >
          {#if asking}<Icon name="spinner" spin size="12px" />{:else}<Icon
              name="paper-plane"
              size="12px"
            />{/if}
          Tanya
        </button>
      </div>

      {#each asks as item}
        <div class="mt-3 border-t pt-2 text-sm">
          <p class="font-medium">{item.q}</p>
          <p class="mt-1 text-ink2">{item.a.answer}</p>
          <p class="mono-label mt-1">Keyakinan {Math.round(item.a.confidence_bp / 100)}%</p>
        </div>
      {/each}
    </div>
  {/if}

  {#if generated.length}
    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Draf soal ({generated.length})</h2>
      <p class="text-xs muted">Draf AI menunggu tinjauanmu sebelum dapat dipublikasikan.</p>
      <ol class="mt-3 space-y-3">
        {#each generated as q, i}
          <li class="border-t pt-2">
            <div class="flex items-start justify-between gap-3">
              <p class="font-medium">{i + 1}. {q.prompt}</p>
              <span
                class="badge"
                class:badge-mint={q.review_status === "approved"}
                class:badge-amber={q.review_status !== "approved"}>{q.review_status}</span
              >
            </div>
            <p class="mt-1 text-sm muted">Kunci: {q.correct_answer}</p>
            {#if q.review_status !== "approved"}
              <button class="btn-ghost mt-2" on:click={() => approve(q)}>Setujui</button>
            {/if}
          </li>
        {/each}
      </ol>
    </div>
  {/if}
</div>
