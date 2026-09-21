<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Attempt, Answer, Exam } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";
  import { statusLabel } from "$lib/utils/format";

  let exam: Exam | null = null;
  let attempt: Attempt | null = null;
  let answers: Answer[] = [];
  let loading = true;
  let error = "";
  let grading = false;

  const examId = $page.params.examId;
  const attemptId = $page.url.searchParams.get("attempt") ?? "";

  async function load() {
    try {
      exam = await api.get<Exam>(`/exams/${examId}`);
      const res = await api.get<{ attempt: Attempt; answers: Answer[] }>(
        `/attempts/${attemptId}/result`,
      );
      attempt = res.attempt;
      answers = res.answers;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat hasil";
    } finally {
      loading = false;
    }
  }

  async function gradeNow() {
    grading = true;
    try {
      await api.post("/ai/grade", { attempt_id: attemptId });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Penilaian gagal";
    } finally {
      grading = false;
    }
  }

  function questionFor(qid: string) {
    return exam?.questions?.find((q) => q.id === qid);
  }

  onMount(load);
</script>

<svelte:head><title>Hasil — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  {#if loading}
    <p class="muted">Memuat hasil…</p>
  {:else if error}
    <p class="alert-error">
      {error}
    </p>
  {:else if attempt}
    <a href={`/exams/${examId}`} class="text-sm text-primary">← Kembali ke ujian</a>
    <div class="card mt-3">
      <div class="flex items-center justify-between">
        <div>
          <p class="mono-label">Hasil Ujian</p>
          <h1 class="mt-2 font-display text-3xl font-bold">Hasil</h1>
          <p class="muted">Percobaan #{attempt.attempt_number} · {statusLabel(attempt.status)}</p>
        </div>
        <div class="text-right">
          <div class="font-display text-3xl font-bold text-primary">
            {bpToPercent(attempt.score_bp)}
          </div>
          {#if attempt.passed !== null && attempt.passed !== undefined}
            <span
              class="badge"
              class:badge-mint={attempt.passed}
              class:badge-magenta={!attempt.passed}
            >
              {attempt.passed ? "Lulus" : "Tidak lulus"}
            </span>
          {/if}
        </div>
      </div>
      {#if attempt.status !== "graded" && (attempt.status === "submitted" || attempt.status === "grading_failed")}
        <button class="btn-primary mt-4" on:click={gradeNow} disabled={grading}>
          {grading ? "Menilai…" : "Nilai sekarang (AI)"}
        </button>
      {/if}
    </div>

    <div class="mt-4 space-y-4">
      {#each answers as a}
        {@const q = questionFor(a.question_id)}
        <div class="card">
          <div class="flex items-start justify-between gap-4">
            <p class="font-medium">{q?.prompt ?? "Soal"}</p>
            <span class="badge badge-indigo">
              {bpToPercent(a.score_bp)} / {bpToPercent(a.max_score_bp, 0)}
            </span>
          </div>
          <p class="mt-3 whitespace-pre-wrap text-sm">{a.answer_text ?? "(tanpa jawaban)"}</p>
          {#if a.feedback}
            <div class="alert-info mt-3">
              <span>
                <strong>Umpan balik AI:</strong>
                {a.feedback}
                {#if a.similarity_bp !== null && a.similarity_bp !== undefined}
                  <span class="muted"> · kemiripan {bpToPercent(a.similarity_bp)}</span>
                {/if}
              </span>
            </div>
          {/if}
          {#if q?.correct_answer}
            <details class="mt-3 text-sm">
              <summary class="cursor-pointer muted">Tampilkan jawaban acuan</summary>
              <p class="mt-2">{q.correct_answer}</p>
            </details>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
