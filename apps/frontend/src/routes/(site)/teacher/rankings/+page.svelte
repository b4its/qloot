<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { RankingResponse } from "$lib/types";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";

  let global: RankingResponse | null = null;
  let loading = true;
  let error = "";

  onMount(async () => {
    try {
      global = await api.get<RankingResponse>("/rankings/global?limit=100");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat peringkat";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>Peringkat Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <p class="mono-label">Panel Guru · Peringkat</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Peringkat</h1>
  <p class="mt-2 muted">Papan peringkat global siswa.</p>

  {#if error}
    <p class="alert-error mt-6">{error}</p>
  {/if}

  {#if loading}
    <div class="mt-6 space-y-2">
      {#each Array(6) as _}<div class="skeleton h-10"></div>{/each}
    </div>
  {:else if global && global.entries.length}
    <div class="card mt-6 overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">#</th><th>Siswa</th><th class="text-right">Skor</th><th
              class="text-right">OPC</th
            ></tr
          >
        </thead>
        <tbody>
          {#each global.entries as e}
            <tr class="border-t">
              <td class="py-1 font-mono">{e.rank}</td>
              <td>{e.display_name ?? `${e.user_id.slice(0, 8)}…`}</td>
              <td class="text-right">{(e.score_bp / 100).toFixed(1)}%</td>
              <td class="text-right font-mono">{formatNumber(e.opc_earned)}</td>
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
