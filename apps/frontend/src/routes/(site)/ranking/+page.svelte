<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { RankingResponse } from "$lib/types";
  import { auth } from "$lib/stores/auth";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";

  let global: RankingResponse | null = null;
  let me: { total_score_bp: number; opc_balance: number } | null = null;
  let loading = true;
  let error = "";

  const medal: Record<number, string> = { 1: "medal", 2: "medal", 3: "medal" };
  const medalColor: Record<number, string> = {
    1: "text-highlight",
    2: "text-ink2",
    3: "text-tertiary",
  };

  onMount(async () => {
    try {
      [global, me] = await Promise.all([
        api.get<RankingResponse>("/rankings/global"),
        api.get<{ total_score_bp: number; opc_balance: number }>("/rankings/me"),
      ]);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat peringkat";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>Peringkat — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <p class="mono-label">Papan Peringkat</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Peringkat global</h1>

  {#if error}
    <p class="alert-error mt-4">{error}</p>
  {/if}

  {#if me}
    <div class="mt-6 card flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-4">
        <span class="tile h-12 w-12">
          <Icon name="user-astronaut" size="20px" />
        </span>
        <div>
          <p class="mono-label">Peringkatmu</p>
          <p class="font-display text-2xl font-bold">{(me.total_score_bp / 100).toFixed(0)}%</p>
        </div>
      </div>
      <div class="text-right">
        <p class="mono-label">OPC diperoleh</p>
        <p class="font-display text-2xl font-bold text-highlight">{formatNumber(me.opc_balance)}</p>
      </div>
    </div>
  {/if}

  {#if loading}
    <div class="mt-6 space-y-2">
      {#each Array(5) as _}<div class="skeleton h-12 w-full"></div>{/each}
    </div>
  {:else if global && global.entries.length}
    <div class="mt-6 card overflow-x-auto !p-0">
      <table class="w-full text-sm">
        <thead class="text-left">
          <tr class="mono-label border-b">
            <th class="px-5 py-3">#</th>
            <th class="px-5 py-3">Pengguna</th>
            <th class="px-5 py-3 text-right">Skor</th>
            <th class="px-5 py-3 text-right">OPC</th>
          </tr>
        </thead>
        <tbody>
          {#each global.entries as e}
            <tr class="border-b last:border-0" class:row-me={e.user_id === $auth.user?.id}>
              <td class="px-5 py-3">
                {#if e.rank <= 3}
                  <Icon name={medal[e.rank]} size="14px" class={medalColor[e.rank]} />
                {:else}
                  <span class="mono">{e.rank}</span>
                {/if}
              </td>
              <td class="px-5 py-3 font-mono text-xs">{e.user_id.slice(0, 8)}…</td>
              <td class="px-5 py-3 text-right">{(e.score_bp / 100).toFixed(1)}%</td>
              <td class="px-5 py-3 text-right font-mono">{formatNumber(e.opc_earned)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div class="card mt-6 grid place-items-center py-14 text-center">
      <Icon name="ranking-star" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada data peringkat</p>
    </div>
  {/if}
</div>
