<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Winner } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { bpToPercent, formatDate } from "$lib/utils/format";

  let quests: Quest[] = [];
  let winnersByQuest: Record<string, Winner[]> = {};
  let loading = true;
  let error = "";
  $: canManage = hasRole($auth.user, "teacher");

  async function load() {
    try {
      quests = await api.get<Quest[]>("/quests");
      for (const q of quests) {
        if (q.status === "finalized") {
          winnersByQuest[q.id] = await api.get<Winner[]>(`/quests/${q.id}/winners`);
        }
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load quests";
    } finally {
      loading = false;
    }
  }

  async function finalize(q: Quest) {
    await api.post(`/quests/${q.id}/finalize`);
    await load();
  }
  async function publish(q: Quest) {
    await api.post(`/quests/${q.id}/publish`);
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>Quests — QLoot</title></svelte:head>

<div class="flex items-center justify-between">
  <h1 class="text-2xl font-bold">Quests</h1>
  {#if canManage}<a href="/teacher/quests" class="btn-primary">＋ Manage quests</a>{/if}
</div>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-tertiary dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading quests…</p>
{:else if quests.length === 0}
  <div class="card mt-6 text-center"><p class="muted">No quests yet.</p></div>
{:else}
  <div class="mt-6 grid gap-4 lg:grid-cols-2">
    {#each quests as q}
      <div class="card">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">{q.title}</h2>
          <span
            class="badge"
            class:bg-green-100={q.status === "open"}
            class:text-secondary={q.status === "open"}>{q.status}</span
          >
        </div>
        <p class="mt-1 text-sm muted">{q.description ?? "Speed quest for top finishers."}</p>
        {#if q.rules?.length}
          <ul class="mt-3 space-y-1 text-sm">
            {#each q.rules as r}
              <li class="flex justify-between">
                <span>Rank {r.rank}</span>
                <span class="font-mono text-highlight">{r.reward_amount} OPC</span>
              </li>
            {/each}
          </ul>
        {/if}
        {#if q.closes_at}
          <p class="mt-2 text-xs muted">Closes {formatDate(q.closes_at)}</p>
        {/if}

        {#if q.status === "finalized" && winnersByQuest[q.id]?.length}
          <div class="mt-3 border-t pt-3">
            <h3 class="flex items-center gap-2 text-sm font-medium">
              <Icon name="trophy" size="12px" class="text-highlight" /> Pemenang
            </h3>
            <ol class="mt-1 space-y-1 text-sm">
              {#each winnersByQuest[q.id] as w}
                <li class="flex justify-between">
                  <span>#{w.rank} · <span class="font-mono">{w.user_id.slice(0, 8)}…</span></span>
                  <span>{bpToPercent(w.score_bp)} · {w.reward_amount} OPC</span>
                </li>
              {/each}
            </ol>
          </div>
        {/if}

        {#if canManage}
          <div class="mt-3 flex gap-2">
            {#if q.status !== "open"}<button class="btn-ghost" on:click={() => publish(q)}
                >Publish</button
              >{/if}
            {#if q.status !== "finalized"}<button class="btn-primary" on:click={() => finalize(q)}
                >Finalize winners</button
              >{/if}
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
