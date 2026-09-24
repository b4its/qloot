<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { LevelLeaderboard, RankingMe, RankingResponse } from "$lib/types";
  import { auth } from "$lib/stores/auth";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import Pagination from "$lib/components/Pagination.svelte";

  type RankingPeriod = "all" | "weekly" | "monthly";

  const PAGE = 25;
  let global: RankingResponse | null = null;
  let me: RankingMe | null = null;
  let levels: LevelLeaderboard | null = null;
  let loading = true;
  let error = "";
  let rankPage = 1;
  let rankHasMore = false;
  let rankLoading = false;
  let levelPage = 1;
  let levelHasMore = false;
  let levelLoading = false;
  let period: RankingPeriod = "all";

  const periodLabel: Record<RankingPeriod, string> = {
    all: "Sepanjang waktu",
    weekly: "Minggu ini",
    monthly: "Bulan ini",
  };

  const medal: Record<number, string> = { 1: "medal", 2: "medal", 3: "medal" };
  const medalColor: Record<number, string> = {
    1: "text-highlight",
    2: "text-ink2",
    3: "text-tertiary",
  };

  async function loadRanking() {
    rankLoading = true;
    try {
      const res = await api.get<RankingResponse>(
        `/rankings/global?limit=${PAGE}&offset=${(rankPage - 1) * PAGE}&period=${period}`,
      );
      global = res;
      rankHasMore = res.entries.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat peringkat";
    } finally {
      rankLoading = false;
    }
  }

  function goRank(delta: number) {
    const next = rankPage + delta;
    if (next < 1 || (delta > 0 && !rankHasMore)) return;
    rankPage = next;
    loadRanking();
  }

  async function changePeriod(next: RankingPeriod) {
    if (next === period) return;
    period = next;
    rankPage = 1;
    await Promise.all([
      loadRanking(),
      api
        .get<RankingMe>(`/rankings/me?period=${period}`)
        .then((m) => (me = m))
        .catch(() => {}),
    ]);
  }

  async function loadLevels() {
    levelLoading = true;
    try {
      const res = await api.get<LevelLeaderboard>(
        `/gamification/levels?limit=${PAGE}&offset=${(levelPage - 1) * PAGE}`,
      );
      levels = res;
      levelHasMore = res.entries.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat peringkat";
    } finally {
      levelLoading = false;
    }
  }

  function goLevel(delta: number) {
    const next = levelPage + delta;
    if (next < 1 || (delta > 0 && !levelHasMore)) return;
    levelPage = next;
    loadLevels();
  }

  onMount(async () => {
    try {
      me = await api.get<RankingMe>(`/rankings/me?period=${period}`);
      await Promise.all([loadRanking(), loadLevels()]);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat peringkat";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>Peringkat — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Papan Peringkat</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Peringkat global</h1>
    </div>
    <div class="flex gap-1 rounded-sm border p-1" role="tablist" aria-label="Periode peringkat">
      {#each ["all", "weekly", "monthly"] as const as p}
        <button
          role="tab"
          aria-selected={period === p}
          class="btn-ghost !px-3 !py-1.5 text-xs"
          class:bg-primary={period === p}
          class:text-white={period === p}
          on:click={() => changePeriod(p)}
        >
          {periodLabel[p]}
        </button>
      {/each}
    </div>
  </div>

  {#if error}
    <p class="alert-error mt-4">{error}</p>
  {/if}

  {#if me}
    <div class="mt-6 card space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-4">
          <span class="tile h-12 w-12">
            <Icon name="user-astronaut" size="20px" />
          </span>
          <div>
            <p class="mono-label">Peringkatmu</p>
            <p class="font-display text-2xl font-bold">
              #{me.rank ?? "—"} ·
              <span class="text-primary">{(me.total_score_bp / 100).toFixed(0)}%</span>
            </p>
          </div>
        </div>
        <div class="flex items-center gap-6 text-right">
          {#if me.level != null}
            <div>
              <p class="mono-label">Level</p>
              <p class="font-display text-2xl font-bold text-primary">{me.level}</p>
            </div>
          {/if}
          {#if me.xp != null}
            <div>
              <p class="mono-label">XP</p>
              <p class="font-display text-2xl font-bold">{formatNumber(me.xp)}</p>
            </div>
          {/if}
          <div>
            <p class="mono-label">OPT diperoleh</p>
            <p class="font-display text-2xl font-bold text-highlight">
              {formatNumber(me.opc_balance)}
            </p>
          </div>
        </div>
      </div>
      {#if me.level != null && me.level_progress != null}
        <div>
          <div class="flex items-center justify-between text-xs">
            <span class="muted">Progres ke level {me.level + 1}</span>
            <span class="mono">{(me.level_progress * 100).toFixed(0)}%</span>
          </div>
          <div
            class="mt-2 h-2 w-full overflow-hidden rounded-full"
            style="background: rgb(var(--line))"
          >
            <div
              class="h-full rounded-full bg-primary transition-all"
              style={`width: ${Math.min(100, Math.max(0, me.level_progress * 100))}%`}
            ></div>
          </div>
        </div>
      {/if}
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
            <th class="px-5 py-3 text-right">OPT</th>
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
              <td class="px-5 py-3">
                {#if e.display_name}
                  <span class="font-medium">{e.display_name}</span>
                {:else}
                  <span class="font-mono text-xs">{e.user_id.slice(0, 8)}…</span>
                {/if}
              </td>
              <td class="px-5 py-3 text-right">{(e.score_bp / 100).toFixed(1)}%</td>
              <td class="px-5 py-3 text-right font-mono">{formatNumber(e.opc_earned)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <Pagination
      page={rankPage}
      pageSize={PAGE}
      hasMore={rankHasMore}
      loading={rankLoading}
      label="peringkat"
      onPrev={() => goRank(-1)}
      onNext={() => goRank(1)}
    />
  {:else}
    <div class="card mt-6 grid place-items-center py-14 text-center">
      <Icon name="ranking-star" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada data peringkat</p>
    </div>
  {/if}

  {#if levels && levels.entries.length}
    <p class="mono-label mt-10">Peringkat Level (XP)</p>
    <h2 class="mt-2 font-display text-2xl font-bold">Papan XP global</h2>
    <div class="mt-4 card overflow-x-auto !p-0">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b text-left">
            <th class="px-5 py-3 font-medium">#</th>
            <th class="px-5 py-3 font-medium">Pengguna</th>
            <th class="px-5 py-3 text-right font-medium">Level</th>
            <th class="px-5 py-3 text-right font-medium">XP</th>
          </tr>
        </thead>
        <tbody>
          {#each levels.entries as e (e.user_id)}
            <tr class="border-b last:border-0">
              <td class="px-5 py-3">
                {#if e.rank <= 3}
                  <Icon name="medal" size="16px" class={medalColor[e.rank]} />
                {:else}
                  <span class="mono">{e.rank}</span>
                {/if}
              </td>
              <td class="px-5 py-3">
                {#if e.display_name}
                  <span class="font-medium">{e.display_name}</span>
                {:else}
                  <span class="font-mono text-xs">{e.user_id.slice(0, 8)}…</span>
                {/if}
              </td>
              <td class="px-5 py-3 text-right font-display font-bold text-primary">{e.level}</td>
              <td class="px-5 py-3 text-right font-mono">{formatNumber(e.xp)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <Pagination
      page={levelPage}
      pageSize={PAGE}
      hasMore={levelHasMore}
      loading={levelLoading}
      label="peringkat level"
      onPrev={() => goLevel(-1)}
      onNext={() => goLevel(1)}
    />
  {/if}
</div>
