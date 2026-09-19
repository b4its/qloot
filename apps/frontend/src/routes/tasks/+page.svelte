<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Task } from "$lib/types";
  import { formatDate } from "$lib/utils/format";

  let tasks: Task[] = [];
  let loading = true;
  let error = "";
  let completed: Record<string, boolean> = {};
  let message = "";

  async function load() {
    try {
      tasks = await api.get<Task[]>("/tasks");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load tasks";
    } finally {
      loading = false;
    }
  }

  async function complete(t: Task) {
    try {
      await api.post(`/tasks/${t.id}/complete`);
      completed[t.id] = true;
      message = `Task complete! +${t.reward_amount} OPC`;
    } catch (e) {
      message = e instanceof ApiError ? e.message : "Could not complete task";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Tasks — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Tasks</h1>
<p class="mt-1 muted">Complete tasks to earn OPC. Daily, weekly and learning tasks.</p>

{#if message}
  <p class="mt-4 rounded-lg bg-primary-50 p-3 text-sm dark:bg-slate-800">{message}</p>
{/if}
{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading tasks…</p>
{:else if tasks.length === 0}
  <div class="card mt-6 text-center"><p class="muted">No active tasks.</p></div>
{:else}
  <div class="mt-6 space-y-3">
    {#each tasks as t}
      <div class="card flex items-center justify-between">
        <div>
          <div class="flex items-center gap-2">
            <h2 class="font-medium">{t.title}</h2>
            <span class="badge bg-slate-100 dark:bg-slate-800">{t.kind}</span>
          </div>
          <p class="text-sm muted">{t.description ?? ""}</p>
          {#if t.ends_at}<p class="text-xs muted">Ends {formatDate(t.ends_at)}</p>{/if}
        </div>
        <div class="text-right">
          <div class="font-mono text-accent-gold">{t.reward_amount} OPC</div>
          {#if completed[t.id]}
            <span class="badge bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-100">✓ Done</span>
          {:else}
            <button class="btn-primary mt-1" on:click={() => complete(t)}>Complete</button>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{/if}
