<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Attempt, Answer, Exam } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";

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
      error = e instanceof ApiError ? e.message : "Failed to load result";
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
      error = e instanceof ApiError ? e.message : "Grading failed";
    } finally {
      grading = false;
    }
  }

  function questionFor(qid: string) {
    return exam?.questions?.find((q) => q.id === qid);
  }

  onMount(load);
</script>

<svelte:head><title>Result — QLoot</title></svelte:head>

{#if loading}
  <p class="muted">Loading result…</p>
{:else if error}
  <p class="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{:else if attempt}
  <a href={`/exams/${examId}`} class="text-sm text-primary-600">← Back to exam</a>
  <div class="card mt-3">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">Result</h1>
        <p class="muted">Attempt #{attempt.attempt_number} · {attempt.status}</p>
      </div>
      <div class="text-right">
        <div class="text-3xl font-bold text-primary-600">{bpToPercent(attempt.score_bp)}</div>
        {#if attempt.passed !== null && attempt.passed !== undefined}
          <span
            class="badge"
            class:bg-green-100={attempt.passed}
            class:text-green-700={attempt.passed}
            class:bg-red-100={!attempt.passed}
            class:text-red-700={!attempt.passed}
          >
            {attempt.passed ? "Passed" : "Not passed"}
          </span>
        {/if}
      </div>
    </div>
    {#if attempt.status !== "graded" && (attempt.status === "submitted" || attempt.status === "grading_failed")}
      <button class="btn-primary mt-4" on:click={gradeNow} disabled={grading}>
        {grading ? "Grading…" : "Grade now (AI)"}
      </button>
    {/if}
  </div>

  <div class="mt-4 space-y-4">
    {#each answers as a}
      {@const q = questionFor(a.question_id)}
      <div class="card">
        <div class="flex items-start justify-between gap-4">
          <p class="font-medium">{q?.prompt ?? "Question"}</p>
          <span
            class="badge bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-100"
          >
            {bpToPercent(a.score_bp)} / {bpToPercent(a.max_score_bp, 0)}
          </span>
        </div>
        <p class="mt-3 whitespace-pre-wrap text-sm">{a.answer_text ?? "(no answer)"}</p>
        {#if a.feedback}
          <div class="mt-3 rounded-lg bg-primary-50 p-3 text-sm dark:bg-slate-800">
            <strong>AI feedback:</strong>
            {a.feedback}
            {#if a.similarity_bp !== null && a.similarity_bp !== undefined}
              <span class="muted"> · similarity {bpToPercent(a.similarity_bp)}</span>
            {/if}
          </div>
        {/if}
        {#if q?.correct_answer}
          <details class="mt-3 text-sm">
            <summary class="cursor-pointer muted">Show reference answer</summary>
            <p class="mt-2">{q.correct_answer}</p>
          </details>
        {/if}
      </div>
    {/each}
  </div>
{/if}
