<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";

  let exams: Exam[] = [];
  let loading = true;
  let error = "";
  $: canManage = hasRole($auth.user, "teacher");

  async function load() {
    try {
      exams = await api.get<Exam[]>("/exams");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load exams";
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Exams — QLoot</title></svelte:head>

<div class="flex items-center justify-between">
  <h1 class="text-2xl font-bold">Exams</h1>
  {#if canManage}<a href="/teacher/exams" class="btn-primary">＋ Manage exams</a>{/if}
</div>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-tertiary dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading exams…</p>
{:else if exams.length === 0}
  <div class="card mt-6 text-center"><p class="muted">No exams available.</p></div>
{:else}
  <div class="mt-6 grid gap-4 sm:grid-cols-2">
    {#each exams as exam}
      <a href={`/exams/${exam.id}`} class="card block transition hover:border-primary">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">{exam.title}</h2>
          <span
            class="badge"
            class:bg-green-100={exam.is_active}
            class:text-secondary={exam.is_active}
          >
            {exam.is_active ? "open" : exam.status}
          </span>
        </div>
        <p class="mt-1 text-sm muted">
          {exam.duration_minutes} min · pass {(exam.passing_score_bp / 100).toFixed(0)}%
        </p>
      </a>
    {/each}
  </div>
{/if}
