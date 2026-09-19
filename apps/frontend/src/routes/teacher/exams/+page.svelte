<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Attempt } from "$lib/types";

  let exams: Exam[] = [];
  let results: Record<string, Attempt[]> = {};
  let newExam = { title: "", duration_minutes: 60, passing_score_bp: 6000 };
  let message = "";
  let error = "";
  let showResults: string | null = null;

  async function load() {
    try {
      exams = await api.get<Exam[]>("/exams");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load exams";
    }
  }

  async function create() {
    error = "";
    try {
      const exam = await api.post<Exam>("/exams", newExam);
      message = `Created "${exam.title}"`;
      newExam = { title: "", duration_minutes: 60, passing_score_bp: 6000 };
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Create failed";
    }
  }

  async function addQuestion(exam: Exam) {
    const prompt = window.prompt("Question prompt:");
    if (!prompt) return;
    const correct = window.prompt("Reference answer:") ?? "";
    await api.post(`/exams/${exam.id}/questions`, { prompt, correct_answer: correct });
    await load();
  }

  async function togglePublish(exam: Exam) {
    if (exam.is_active) await api.post(`/exams/${exam.id}/close`);
    else await api.post(`/exams/${exam.id}/publish`);
    await load();
  }

  async function viewResults(exam: Exam) {
    showResults = exam.id;
    results[exam.id] = await api.get<Attempt[]>(`/exams/${exam.id}/results`);
  }

  onMount(load);
</script>

<svelte:head><title>Exams (Teacher) — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Manage Exams</h1>

{#if message}<p class="mt-4 rounded-lg bg-primary-50 p-3 text-sm dark:bg-slate-800">{message}</p>{/if}
{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>
{/if}

<div class="card mt-4">
  <h2 class="font-semibold">New exam</h2>
  <div class="mt-3 grid gap-3 sm:grid-cols-3">
    <input class="input sm:col-span-1" placeholder="Title" bind:value={newExam.title} />
    <input class="input" type="number" min="1" bind:value={newExam.duration_minutes} />
    <input class="input" type="number" min="0" max="10000" bind:value={newExam.passing_score_bp} />
  </div>
  <p class="mt-1 text-xs muted">Duration in minutes · passing score in basis points (6000 = 60%)</p>
  <button class="btn-primary mt-3" on:click={create} disabled={newExam.title.length < 2}>Create exam</button>
</div>

<div class="mt-6 space-y-4">
  {#each exams as exam}
    <div class="card">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="font-semibold">{exam.title}</h2>
          <p class="text-sm muted">
            {exam.questions?.length ?? 0} questions · {exam.duration_minutes} min · pass {(exam.passing_score_bp / 100).toFixed(0)}%
          </p>
        </div>
        <div class="flex gap-2">
          <button class="btn-ghost" on:click={() => addQuestion(exam)}>＋ Question</button>
          <button class="btn-ghost" on:click={() => viewResults(exam)}>Results</button>
          <button class="btn-primary" on:click={() => togglePublish(exam)}>
            {exam.is_active ? "Close" : "Publish"}
          </button>
        </div>
      </div>

      {#if showResults === exam.id}
        <div class="mt-3 border-t pt-3">
          <h3 class="text-sm font-medium">Participant results</h3>
          <ul class="mt-1 space-y-1 text-sm">
            {#each results[exam.id] ?? [] as a}
              <li class="flex justify-between">
                <span class="font-mono">{a.user_id.slice(0, 8)}…</span>
                <span>{a.score_bp !== null && a.score_bp !== undefined ? (a.score_bp / 100).toFixed(1) + "%" : a.status}</span>
              </li>
            {/each}
            {#if !(results[exam.id]?.length)}<li class="muted">No submissions yet.</li>{/if}
          </ul>
        </div>
      {/if}
    </div>
  {/each}
  {#if exams.length === 0}<p class="muted">No exams yet.</p>{/if}
</div>
