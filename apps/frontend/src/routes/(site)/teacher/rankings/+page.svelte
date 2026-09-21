<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { RankingResponse } from "$lib/types";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";

  const PAGE = 25;
  let global: RankingResponse | null = null;
  let loading = true;
  let error = "";
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    try {
      global = await api.get<RankingResponse>(
        `/rankings/global?limit=${PAGE}&offset=${(page - 1) * PAGE}`,
      );
      hasMore = global.entries.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat peringkat";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    page = next;
    load();
  }

  onMount(load);
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
    <Pagination
      {page}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="siswa"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {:else}
    <div class="card mt-6 grid place-items-center py-14 text-center">
      <Icon name="ranking-star" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada data peringkat</p>
    </div>
  {/if}
</div>
