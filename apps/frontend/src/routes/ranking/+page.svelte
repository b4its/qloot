<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { RankingResponse } from "$lib/types";
  import { auth } from "$lib/stores/auth";
  import { formatNumber } from "$lib/utils/format";

  let global: RankingResponse | null = null;
  let me: { total_score_bp: number; opc_balance: number } | null = null;
  let loading = true;
  let error = "";

  async function load() {
    try {
      global = await api.get<RankingResponse>("/rankings/global");
      me = await api.get("/rankings/me");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load rankings";
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Ranking — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Global Ranking</h1>

{#if me}
  <div class="card mt-4">
    <h2 class="font-semibold">Your standing</h2>
    <div class="mt-2 grid gap-3 sm:grid-cols-2">
      <div>
        <div class="text-2xl font-bold text-primary-600">{(me.total_score_bp / 100).toFixed(0)}%</div>
        <div class="text-sm muted">Total score</div>
      </div>
      <div>
        <div class="text-2xl font-bold text-accent-gold">{formatNumber(me.opc_balance)} OPC</div>
        <div class="text-sm muted">OPC earned</div>
      </div>
    </div>
  </div>
{/if}

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading leaderboard…</p>
{:else if global && global.entries.length}
  <div class="card mt-4 overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="text-left muted">
        <tr>
          <th class="py-2">#</th>
          <th>User</th>
          <th class="text-right">Score</th>
          <th class="text-right">OPC</th>
        </tr>
      </thead>
      <tbody>
        {#each global.entries as e}
          <tr
            class="border-t"
            class:bg-primary-50={e.user_id === $auth.user?.id}
            class:dark:bg-slate-800={e.user_id === $auth.user?.id}
          >
            <td class="py-2 font-medium">
              {#if e.rank === 1}🥇{:else if e.rank === 2}🥈{:else if e.rank === 3}🥉{:else}{e.rank}{/if}
            </td>
            <td class="font-mono">{e.user_id.slice(0, 8)}…</td>
            <td class="text-right">{(e.score_bp / 100).toFixed(1)}%</td>
            <td class="text-right font-mono">{formatNumber(e.opc_earned)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{:else}
  <div class="card mt-4 text-center"><p class="muted">No ranking data yet.</p></div>
{/if}
