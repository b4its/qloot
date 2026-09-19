<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Exam, Winner } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";

  let quests: Quest[] = [];
  let exams: Exam[] = [];
  let winners: Record<string, Winner[]> = {};
  let newQuest = { title: "", exam_id: "", top_n_winners: 3, ranks: [100, 60, 40] };
  let message = "";
  let error = "";

  async function load() {
    try {
      quests = await api.get<Quest[]>("/quests");
      exams = await api.get<Exam[]>("/exams");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load quests";
    }
  }

  async function create() {
    error = "";
    try {
      const rules = newQuest.ranks.map((amount, i) => ({ rank: i + 1, reward_amount: amount }));
      await api.post<Quest>("/quests", {
        title: newQuest.title,
        exam_id: newQuest.exam_id || null,
        top_n_winners: newQuest.top_n_winners,
        rules,
      });
      message = "Quest created";
      newQuest.title = "";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Create failed";
    }
  }

  async function finalize(q: Quest) {
    const res = await api.post<{ allocations_created: number }>(`/quests/${q.id}/finalize`);
    message = `Finalized — ${res.allocations_created} rewards allocated`;
    winners[q.id] = await api.get<Winner[]>(`/quests/${q.id}/winners`);
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>Quests (Teacher) — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Manage Quests</h1>
<p class="mt-1 muted">
  Reward the fastest valid finishers. Winners are deterministic: score, then speed, then attempt id.
</p>

{#if message}<p class="mt-4 rounded-lg bg-primary-50 p-3 text-sm dark:bg-slate-800">
    {message}
  </p>{/if}
{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

<div class="card mt-4">
  <h2 class="font-semibold">New quest</h2>
  <div class="mt-3 grid gap-3 sm:grid-cols-2">
    <input class="input" placeholder="Title" bind:value={newQuest.title} />
    <select class="input" bind:value={newQuest.exam_id}>
      <option value="">No linked exam</option>
      {#each exams as e}<option value={e.id}>{e.title}</option>{/each}
    </select>
    <input class="input" type="number" min="1" max="50" bind:value={newQuest.top_n_winners} />
    <div class="flex items-center gap-2">
      {#each newQuest.ranks as amount, i}
        <input class="input w-20" type="number" min="0" bind:value={newQuest.ranks[i]} />
      {/each}
      <span class="text-xs muted">OPC per rank</span>
    </div>
  </div>
  <button class="btn-primary mt-3" on:click={create} disabled={newQuest.title.length < 2}
    >Create quest</button
  >
</div>

<div class="mt-6 space-y-4">
  {#each quests as q}
    <div class="card">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="font-semibold">{q.title}</h2>
          <p class="text-sm muted">Top {q.top_n_winners} · {q.status}</p>
        </div>
        <button
          class="btn-primary"
          on:click={() => finalize(q)}
          disabled={q.status === "finalized"}
        >
          {q.status === "finalized" ? "Finalized" : "Finalize winners"}
        </button>
      </div>
      {#if winners[q.id]?.length}
        <ol class="mt-2 space-y-1 text-sm">
          {#each winners[q.id] as w}
            <li class="flex justify-between">
              <span>#{w.rank} · <span class="font-mono">{w.user_id.slice(0, 8)}…</span></span>
              <span>{bpToPercent(w.score_bp)} · {w.reward_amount} OPC</span>
            </li>
          {/each}
        </ol>
      {/if}
    </div>
  {/each}
  {#if quests.length === 0}<p class="muted">No quests yet.</p>{/if}
</div>
