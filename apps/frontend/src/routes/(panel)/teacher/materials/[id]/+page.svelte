<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Material, Question, SummaryResult, AskResult } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { formatDate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const materialId = $page.params.id;

  let material: Material | null = null;
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";

  // Rename.
  let renameDraft = "";

  // AI question generation.
  let count = 3;
  let generated: Question[] = [];

  // AI study assistant.
  let summary: SummaryResult | null = null;
  let summaryLoading = false;
  let question = "";
  let asking = false;
  let asks: { q: string; a: AskResult }[] = [];

  async function load() {
    loading = true;
    try {
      material = await api.get<Material>(`/materials/${materialId}`);
      renameDraft = material.filename;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat materi";
    } finally {
      loading = false;
    }
  }

  async function saveRename() {
    const name = renameDraft.trim();
    if (name.length < 1) return;
    error = "";
    message = "";
    busy = "rename";
    try {
      material = await api.patch<Material>(`/materials/${materialId}`, { filename: name });
      message = "Nama materi diperbarui.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengganti nama materi";
    } finally {
      busy = "";
    }
  }

  async function generate() {
    error = "";
    message = "";
    generated = [];
    busy = "generate";
    try {
      generated = await api.post<Question[]>(`/materials/${materialId}/generate-questions-sync`, {
        count,
        language: "id",
      });
      message = `Membuat ${generated.length} draf soal — tinjau sebelum dipublikasikan.`;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat soal";
    } finally {
      busy = "";
    }
  }

  async function approve(q: Question) {
    try {
      await api.patch(`/questions/${q.id}`, { review_status: "approved" });
      generated = generated.map((g) => (g.id === q.id ? { ...g, review_status: "approved" } : g));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyetujui";
    }
  }

  async function loadSummary() {
    summaryLoading = true;
    summary = null;
    try {
      summary = await api.get<SummaryResult>(`/materials/${materialId}/summary`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal merangkum materi";
    } finally {
      summaryLoading = false;
    }
  }

  async function ask() {
    if (question.trim().length < 3) return;
    const q = question.trim();
    asking = true;
    try {
      const a = await api.post<AskResult>(`/materials/${materialId}/ask`, { question: q });
      asks = [{ q, a }, ...asks];
      question = "";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menanyakan materi";
    } finally {
      asking = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Kelola Materi — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Materi"
    title={material?.filename ?? "Kelola materi"}
    subtitle="Ganti nama, buat soal dengan AI, dan gunakan asisten materi."
    backHref="/teacher/materials"
    backLabel="Materi"
  />

  <PageAlerts {message} {error} />

  {#if loading}
    <div class="mt-6 space-y-3">
      <div class="skeleton h-24"></div>
      <div class="skeleton h-40"></div>
    </div>
  {:else if material}
    <div class="card mt-6">
      <h2 class="hud font-display text-lg font-bold">Detail materi</h2>
      <p class="mt-1 text-xs muted">{formatDate(material.created_at)} · {material.status}</p>
      <label class="mt-3 block">
        <span class="mono-label">Nama file</span>
        <input class="input mt-1" bind:value={renameDraft} />
      </label>
      <button class="btn-primary mt-3" on:click={saveRename} disabled={busy === "rename"}>
        {busy === "rename" ? "Menyimpan…" : "Simpan nama"}
      </button>
    </div>

    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Buat soal dengan AI</h2>
      <p class="mt-1 text-xs muted">Draf AI menunggu tinjauanmu sebelum dipublikasikan.</p>
      <div class="mt-3 flex items-end gap-2">
        <label class="block w-24">
          <span class="mono-label">Jumlah</span>
          <input class="input mt-1" type="number" min="1" max="20" bind:value={count} />
        </label>
        <button class="btn-secondary" on:click={generate} disabled={busy === "generate"}>
          {#if busy === "generate"}<Icon name="spinner" spin size="12px" />{:else}<Icon
              name="wand-magic-sparkles"
              size="12px"
            />{/if}
          Buat soal
        </button>
      </div>

      {#if generated.length}
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
      {/if}
    </div>

    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Asisten materi</h2>
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
</div>
