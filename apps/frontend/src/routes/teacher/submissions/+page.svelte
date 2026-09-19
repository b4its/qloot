<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { SubmissionRow, TeacherAnalytics } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";

  let rows: SubmissionRow[] = [];
  let analytics: TeacherAnalytics | null = null;
  let loading = true;
  let error = "";

  onMount(async () => {
    try {
      [rows, analytics] = await Promise.all([
        api.get<SubmissionRow[]>("/teacher/submissions"),
        api.get<TeacherAnalytics>("/teacher/analytics"),
      ]);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load submissions";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>Submissions — QLoot Teacher</title></svelte:head>

<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold">Submissions</h1>
    <p class="mt-1 text-sm muted">Recent student answers across your exams with AI feedback.</p>
  </div>
  <a href="/teacher" class="btn-ghost">← Teacher home</a>
</div>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

{#if analytics}
  <div class="mt-4 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
    <div class="card">
      <div class="text-xs muted">Exams</div>
      <div class="text-2xl font-bold">{analytics.exams}</div>
    </div>
    <div class="card">
      <div class="text-xs muted">Graded</div>
      <div class="text-2xl font-bold">{analytics.graded_attempts}</div>
    </div>
    <div class="card">
      <div class="text-xs muted">Avg score</div>
      <div class="text-2xl font-bold">{bpToPercent(analytics.average_score_bp)}</div>
    </div>
    <div class="card">
      <div class="text-xs muted">Pass rate</div>
      <div class="text-2xl font-bold">{bpToPercent(analytics.pass_rate_bp)}</div>
    </div>
    <div class="card">
      <div class="text-xs muted">Winners</div>
      <div class="text-2xl font-bold">{analytics.winners}</div>
    </div>
    <div class="card">
      <div class="text-xs muted">OPC awarded</div>
      <div class="text-2xl font-bold text-accent-gold">{analytics.opc_awarded}</div>
    </div>
  </div>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading…</p>
{:else if !rows.length}
  <div class="card mt-4 text-center"><p class="muted">No submissions yet.</p></div>
{:else}
  <div class="card mt-4 overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="text-left muted">
        <tr
          ><th class="py-1">Exam</th><th>Question</th><th>Answer</th><th class="text-right"
            >Score</th
          ><th>Feedback</th></tr
        >
      </thead>
      <tbody>
        {#each rows as r}
          <tr class="border-t align-top">
            <td class="py-2">{r.exam_title}</td>
            <td class="max-w-[220px]">{r.prompt}</td>
            <td class="max-w-[260px] text-xs muted">{r.answer_text}</td>
            <td class="text-right font-mono">{bpToPercent(r.score_bp)}</td>
            <td class="max-w-[220px] text-xs muted">{r.feedback}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
