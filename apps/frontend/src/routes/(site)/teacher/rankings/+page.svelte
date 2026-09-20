<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api/client";
  import type { RankingResponse } from "$lib/types";
  import { formatNumber } from "$lib/utils/format";

  let global: RankingResponse | null = null;

  onMount(async () => {
    global = await api.get<RankingResponse>("/rankings/global");
  });
</script>

<svelte:head><title>Rankings (Teacher) — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Rankings</h1>

{#if global}
  <div class="card mt-4 overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="text-left muted">
        <tr
          ><th class="py-1">#</th><th>User</th><th class="text-right">Score</th><th
            class="text-right">OPC</th
          ></tr
        >
      </thead>
      <tbody>
        {#each global.entries as e}
          <tr class="border-t">
            <td class="py-1">{e.rank}</td>
            <td class="font-mono">{e.user_id.slice(0, 8)}…</td>
            <td class="text-right">{(e.score_bp / 100).toFixed(1)}%</td>
            <td class="text-right font-mono">{formatNumber(e.opc_earned)}</td>
          </tr>
        {/each}
        {#if global.entries.length === 0}<tr><td colspan="4" class="py-2 muted">No data.</td></tr
          >{/if}
      </tbody>
    </table>
  </div>
{:else}
  <p class="mt-4 muted">Loading…</p>
{/if}
