<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Attempt } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";

  let exam: Exam | null = null;
  let loading = true;
  let error = "";
  let starting = false;
  let pastAttempts: Attempt[] = [];

  const examId = $page.params.examId;
  $: canManage = hasRole($auth.user, "teacher");

  async function load() {
    try {
      exam = await api.get<Exam>(`/exams/${examId}`);
      const attempts = await api.get<Attempt[]>("/attempts");
      pastAttempts = attempts.filter((a) => a.exam_id === examId);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load exam";
    } finally {
      loading = false;
    }
  }

  async function start() {
    starting = true;
    try {
      const attempt = await api.post<Attempt>(`/exams/${examId}/attempts`);
      await goto(`/exams/${examId}/attempt?attempt=${attempt.id}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Could not start attempt";
    } finally {
      starting = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>{exam?.title ?? "Exam"} — QLoot</title></svelte:head>

{#if loading}
  <p class="muted">Loading…</p>
{:else if error}
  <p class="rounded-lg bg-red-50 p-3 text-sm text-tertiary dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{:else if exam}
  <a href="/exams" class="text-sm text-primary">← All exams</a>
  <h1 class="mt-2 text-2xl font-bold">{exam.title}</h1>
  <p class="mt-1 muted">
    Duration: {exam.duration_minutes} min · Passing: {(exam.passing_score_bp / 100).toFixed(0)}% · {exam
      .questions?.length ?? 0} questions
  </p>

  {#if canManage}
    <div class="mt-4 flex gap-2">
      <button class="btn-primary" on:click={() => api.post(`/exams/${examId}/publish`).then(load)}
        >Publish</button
      >
      <button class="btn-ghost" on:click={() => api.post(`/exams/${examId}/close`).then(load)}
        >Close</button
      >
      <a href="/teacher/exams" class="btn-ghost">Edit in Teacher</a>
    </div>
  {/if}

  {#if exam.is_active}
    <div class="card mt-6">
      <h2 class="font-semibold">Ready to take this exam?</h2>
      <p class="mt-1 text-sm muted">
        The timer is server-authoritative. Your answers autosave as you go.
      </p>
      <button class="btn-primary mt-4" on:click={start} disabled={starting}>
        {starting ? "Starting…" : "Start attempt"}
      </button>
    </div>
  {:else}
    <p class="card mt-6 muted">This exam is not currently open.</p>
  {/if}

  {#if pastAttempts.length}
    <div class="card mt-4">
      <h2 class="font-semibold">Your attempts</h2>
      <ul class="mt-2 space-y-2 text-sm">
        {#each pastAttempts as a}
          <li class="flex items-center justify-between">
            <span>Attempt #{a.attempt_number} · {a.status}</span>
            <span>
              {#if a.score_bp !== null && a.score_bp !== undefined}
                {(a.score_bp / 100).toFixed(1)}%
              {/if}
              <a href={`/exams/${examId}/result?attempt=${a.id}`} class="ml-2 text-primary">View</a>
            </span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}
{/if}
