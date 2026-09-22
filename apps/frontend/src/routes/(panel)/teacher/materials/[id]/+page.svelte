<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { api, ApiError, API_BASE } from "$lib/api/client";
  import type {
    Material,
    Question,
    SummaryResult,
    AskResult,
    GenerationJob,
    AIJob,
  } from "$lib/types";
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
  // Async mode: enqueue a job, poll it, then surface the drafts.
  let asyncMode = false;
  let job: AIJob | null = null;
  let jobTimer: ReturnType<typeof setTimeout> | null = null;
  let regenerating = "";

  // AI study assistant.
  let summary: SummaryResult | null = null;
  let summaryLoading = false;
  let question = "";
  let asking = false;
  let asks: { q: string; a: AskResult }[] = [];

  function stopPolling() {
    if (jobTimer) {
      clearTimeout(jobTimer);
      jobTimer = null;
    }
  }

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
    if (!(count >= 1 && count <= 20)) {
      error = "Jumlah soal harus antara 1 dan 20.";
      return;
    }
    generated = [];
    job = null;
    stopPolling();
    if (asyncMode) {
      await generateAsync();
      return;
    }
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

  /** Enqueue an async generation job, then poll until it finishes. */
  async function generateAsync() {
    busy = "generate";
    try {
      const enq = await api.post<GenerationJob>(`/materials/${materialId}/generate-questions`, {
        count,
        language: "id",
      });
      message = "Pekerjaan pembuatan soal diantrekan…";
      pollJob(enq.job_id);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengantrekan pembuatan soal";
      busy = "";
    }
  }

  function pollJob(jobId: string) {
    stopPolling();
    jobTimer = setTimeout(async () => {
      try {
        const j = await api.get<AIJob>(`/ai/jobs/${jobId}`);
        job = j;
        if (j.status === "done") {
          busy = "";
          message = "Soal selesai dibuat — muat ulang draf untuk meninjau.";
          await loadDrafts();
        } else if (j.status === "failed") {
          busy = "";
          error = j.error_message || "Pembuatan soal gagal";
        } else {
          pollJob(jobId);
        }
      } catch (e) {
        busy = "";
        error = e instanceof ApiError ? e.message : "Gagal memeriksa status pekerjaan";
      }
    }, 1500);
  }

  /** Load the teacher's own draft (pending) questions for this material. */
  async function loadDrafts() {
    try {
      const detail = await api.get<Question[]>(`/materials/${materialId}/questions`);
      generated = detail;
    } catch {
      /* endpoint optional; leave the drafts as-is */
    }
  }

  /** Ask the AI to regenerate a question from its source material. */
  async function regenerate(q: Question) {
    regenerating = q.id;
    error = "";
    try {
      const j = await api.post<AIJob>(`/ai/questions/${q.id}/regenerate`);
      job = j;
      // Replace the stale draft with the freshly generated sibling.
      generated = generated.filter((g) => g.id !== q.id);
      message = "Membuat ulang soal…";
      pollJobForDrafts(j.id);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat ulang soal";
      regenerating = "";
    }
  }

  function pollJobForDrafts(jobId: string) {
    stopPolling();
    jobTimer = setTimeout(async () => {
      try {
        const j = await api.get<AIJob>(`/ai/jobs/${jobId}`);
        job = j;
        if (j.status === "done") {
          regenerating = "";
          message = "Soal dibuat ulang.";
          await loadDrafts();
        } else if (j.status === "failed") {
          regenerating = "";
          error = j.error_message || "Pembuatan ulang gagal";
        } else {
          pollJobForDrafts(jobId);
        }
      } catch (e) {
        regenerating = "";
        error = e instanceof ApiError ? e.message : "Gagal membuat ulang soal";
      }
    }, 1500);
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
  onDestroy(stopPolling);
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
      <a
        class="btn-ghost mt-3 ml-2"
        href={`${API_BASE}/api/v1/materials/${materialId}/download`}
        target="_blank"
        rel="noopener"
      >
        <Icon name="download" size="11px" /> Unduh PDF
      </a>
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
        <label class="mb-1 flex items-center gap-2 text-xs muted">
          <input type="checkbox" bind:checked={asyncMode} />
          Antrean (async)
        </label>
      </div>

      {#if job}
        <p class="mono-label mt-2">
          Pekerjaan {job.kind} · {job.status}
          {#if job.attempts > 1}· percobaan {job.attempts}{/if}
        </p>
      {/if}

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
              <div class="mt-2 flex gap-2">
                {#if q.review_status !== "approved"}
                  <button class="btn-ghost" on:click={() => approve(q)}>Setujui</button>
                {/if}
                <button
                  class="btn-ghost"
                  on:click={() => regenerate(q)}
                  disabled={regenerating === q.id}
                >
                  {#if regenerating === q.id}<Icon name="spinner" spin size="11px" />{:else}<Icon
                      name="rotate"
                      size="11px"
                    />{/if}
                  Buat ulang
                </button>
              </div>
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
