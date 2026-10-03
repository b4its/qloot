<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { LevelLeaderboard, RankingMe, RankingResponse } from "$lib/types";
  import { auth } from "$lib/stores/auth";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";

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
  let levelError = "";
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
    error = "";
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
    // Reset the caller's row so a failed fetch can never show the previous
    // period's rank as if it belonged to the new one.
    me = null;
    meLoading = true;
    await Promise.all([
      loadRanking(),
      api
        .get<RankingMe>(`/rankings/me?period=${period}`)
        .then((m) => (me = m))
        .catch(() => {
          me = null;
        })
        .finally(() => (meLoading = false)),
    ]);
  }
  let meLoading = false;

  async function loadLevels() {
    levelLoading = true;
    levelError = "";
    try {
      const res = await api.get<LevelLeaderboard>(
        `/gamification/levels?limit=${PAGE}&offset=${(levelPage - 1) * PAGE}`,
      );
      levels = res;
      levelHasMore = res.entries.length === PAGE;
    } catch (e) {
      levelError = e instanceof ApiError ? e.message : "Gagal memuat peringkat level";
    } finally {
      levelLoading = false;
    }
  }

  // --- search + metrics over the loaded page ---------------------------------
  let query = "";
  $: q = query.toLowerCase().trim();
  $: visibleEntries = global
    ? global.entries.filter((e) => !q || (e.display_name ?? e.user_id).toLowerCase().includes(q))
    : [];
  $: pageTopScore =
    global && global.entries.length ? Math.max(...global.entries.map((e) => e.score_bp)) / 100 : 0;
  $: pageAvgScore =
    global && global.entries.length
      ? global.entries.reduce((s, e) => s + e.score_bp, 0) / global.entries.length / 100
      : 0;
  $: myEntry = global?.entries.find((e) => e.user_id === $auth.user?.id) ?? null;

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

<svelte:head><title>Peringkat | QLoot</title></svelte:head>

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
          class:text-[#05060A]={period === p}
          on:click={() => changePeriod(p)}
        >
          {periodLabel[p]}
        </button>
      {/each}
    </div>
  </div>

  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">{error}</p>
  {/if}

  {#if meLoading}
    <div class="mt-6 card"><div class="skeleton h-24"></div></div>
  {:else if me}
    <div class="mt-6 card space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-4">
          <span class="tile h-12 w-12">
            <Icon name="user-astronaut" size="20px" />
          </span>
          <div>
            <p class="mono-label">Peringkatmu</p>
            <p class="font-display text-2xl font-bold">
              #{me.rank ?? "-"} ·
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
            role="progressbar"
            aria-valuenow={Math.round(Math.min(100, Math.max(0, me.level_progress * 100)))}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Progres ke level ${me.level + 1}`}
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
    <!-- Metrics + search -->
    <MetricStrip
      metrics={[
        { label: "Di halaman ini", value: global.entries.length },
        {
          label: "Skor tertinggi",
          value: `${pageTopScore.toFixed(1)}%`,
          tone: "text-highlight",
          role: "top-score",
        },
        { label: "Rata-rata halaman", value: `${pageAvgScore.toFixed(1)}%` },
        { label: "Peringkatmu", value: `#${me?.rank ?? "-"}`, tone: "text-primary" },
      ]}
    />

    <div class="mt-4 flex flex-wrap items-center gap-2">
      <div class="w-full sm:w-64">
        <SearchInput bind:value={query} placeholder="Cari nama pengguna..." label="Cari pengguna" />
      </div>
      {#if myEntry && !q}
        <span class="badge badge-indigo">Barismu ditandai</span>
      {/if}
    </div>

    <div class="mt-4 card overflow-x-auto !p-0">
      <table class="w-full text-sm">
        <caption class="sr-only">Peringkat global</caption>
        <thead class="text-left">
          <tr class="mono-label border-b">
            <th class="px-5 py-3" scope="col">#</th>
            <th class="px-5 py-3" scope="col">Pengguna</th>
            <th class="px-5 py-3 text-right" scope="col">Skor</th>
            <th class="px-5 py-3 text-right" scope="col">OPT</th>
          </tr>
        </thead>
        <tbody>
          {#if visibleEntries.length === 0}
            <tr
              ><td colspan="4" class="px-5 py-6 text-center muted">
                Tidak ada pengguna yang cocok dengan pencarianmu.
              </td></tr
            >
          {/if}
          {#each visibleEntries as e (e.user_id)}
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
    <EmptyState
      icon="ranking-star"
      title="Belum ada data peringkat"
      description="Papan peringkat akan terisi begitu ada aktivitas belajar."
    />
  {/if}

  {#if levels && levels.entries.length}
    <p class="mono-label mt-10">Peringkat Level (XP)</p>
    <h2 class="mt-2 font-display text-2xl font-bold">Papan XP global</h2>
    <div class="mt-4 card overflow-x-auto !p-0">
      <table class="w-full text-sm">
        <caption class="sr-only">Papan XP global</caption>
        <thead>
          <tr class="border-b text-left">
            <th class="px-5 py-3 font-medium" scope="col">#</th>
            <th class="px-5 py-3 font-medium" scope="col">Pengguna</th>
            <th class="px-5 py-3 text-right font-medium" scope="col">Level</th>
            <th class="px-5 py-3 text-right font-medium" scope="col">XP</th>
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
  {:else if levelError}
    <EmptyState
      tone="error"
      icon="triangle-exclamation"
      title="Gagal memuat papan XP"
      description={levelError}
      actionLabel="Coba lagi"
      onAction={loadLevels}
    />
  {:else if levelLoading}
    <div class="mt-10 space-y-2">
      {#each Array(4) as _}<div class="skeleton h-10"></div>{/each}
    </div>
  {:else}
    <EmptyState
      icon="ranking-star"
      title="Belum ada data XP"
      description="Belum ada data XP untuk ditampilkan."
    />
  {/if}
</div>
