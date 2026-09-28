<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { RankingResponse } from "$lib/types";
  import { formatNumber } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import { reveal } from "$lib/actions/reveal";

  // Redirect once auth resolves; a mount-only check could fire before the
  // session loaded, briefly exposing teacher-only UI.
  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  type Period = "all" | "weekly" | "monthly";
  const PAGE = 25;

  let entries: RankingResponse["entries"] = [];
  let loading = true;
  let error = "";
  let page = 1;
  let hasMore = false;
  let period: Period = "all";
  let query = "";
  let sortBy: "rank" | "score" | "opc" | "name" = "rank";

  const periodLabel: Record<Period, string> = {
    all: "Sepanjang waktu",
    weekly: "Minggu ini",
    monthly: "Bulan ini",
  };
  const medalColor: Record<number, string> = {
    1: "text-highlight",
    2: "text-ink2",
    3: "text-tertiary",
  };

  async function load() {
    loading = true;
    error = "";
    try {
      const res = await api.get<RankingResponse>(
        `/rankings/global?limit=${PAGE}&offset=${(page - 1) * PAGE}&period=${period}`,
      );
      entries = res.entries;
      hasMore = res.entries.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat peringkat";
    } finally {
      loading = false;
    }
  }

  async function changePeriod(next: Period) {
    if (next === period) return;
    period = next;
    page = 1;
    await load();
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    page = next;
    load();
  }

  // --- search + sort (client-side over the loaded page) ----------------------
  $: displayed = entries
    .filter((e) => {
      if (!query.trim()) return true;
      const q = query.toLowerCase().trim();
      return (e.display_name ?? e.user_id).toLowerCase().includes(q);
    })
    .sort((a, b) => {
      if (sortBy === "score") return b.score_bp - a.score_bp;
      if (sortBy === "opc") return b.opc_earned - a.opc_earned;
      if (sortBy === "name")
        return (a.display_name ?? a.user_id).localeCompare(b.display_name ?? b.user_id);
      return a.rank - b.rank;
    });

  // --- summary metrics over the loaded page ----------------------------------
  $: avgScore = entries.length
    ? entries.reduce((s, e) => s + e.score_bp, 0) / entries.length / 100
    : 0;
  $: topScore = entries.length ? Math.max(...entries.map((e) => e.score_bp)) / 100 : 0;
  $: totalOpc = entries.reduce((s, e) => s + e.opc_earned, 0);
  $: passing = entries.filter((e) => e.score_bp >= 6000).length;

  onMount(load);
</script>

<svelte:head><title>Peringkat — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Peringkat"
    title="Peringkat Siswa"
    subtitle="Papan peringkat global siswa. Saring per periode dan cari siswa tertentu."
    backHref="/teacher"
    backLabel="Panel Guru"
  />

  {#if error}
    <p class="alert-error mt-6" role="alert" aria-live="assertive">{error}</p>
  {/if}

  <!-- Period tabs -->
  <div
    class="mt-6 flex flex-wrap gap-1 rounded-sm border p-1 w-fit"
    role="tablist"
    aria-label="Periode"
  >
    {#each ["all", "weekly", "monthly"] as const as p}
      <button
        role="tab"
        aria-selected={period === p}
        class="btn-ghost !px-3 !py-1.5 text-xs"
        class:bg-primary={period === p}
        class:!text-[#05060A]={period === p}
        on:click={() => changePeriod(p)}
      >
        {periodLabel[p]}
      </button>
    {/each}
  </div>

  {#if loading}
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {#each Array(4) as _}<div class="skeleton h-24"></div>{/each}
    </div>
    <div class="mt-6 space-y-2">
      {#each Array(6) as _}<div class="skeleton h-10"></div>{/each}
    </div>
  {:else if entries.length === 0}
    <div class="card mt-6 grid place-items-center py-14 text-center">
      <Icon name="ranking-star" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada data peringkat</p>
      <p class="text-sm muted">Peringkat muncul setelah siswa mengerjakan ujian.</p>
    </div>
  {:else}
    <!-- Overview metrics (over the current page) -->
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Skor tertinggi (halaman ini)</p>
        <p class="mt-1 font-display text-3xl font-bold text-highlight" data-role="top-score">
          {topScore.toFixed(1)}%
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Rata-rata (halaman ini)</p>
        <p class="mt-1 font-display text-3xl font-bold" data-role="avg-score">
          {avgScore.toFixed(1)}%
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Lulus (≥60%)</p>
        <p class="mt-1 font-display text-3xl font-bold text-mint">{passing}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">OPT diperoleh (halaman ini)</p>
        <p class="mt-1 font-display text-3xl font-bold text-secondary">{formatNumber(totalOpc)}</p>
      </div>
    </div>

    <!-- Search + sort -->
    <div class="mt-6 flex flex-wrap items-center gap-3">
      <div class="relative flex-1 min-w-[220px]">
        <Icon
          name="magnifying-glass"
          size="13px"
          class="absolute left-3 top-1/2 -translate-y-1/2 muted"
        />
        <input
          class="input !pl-9"
          placeholder="Cari siswa…"
          bind:value={query}
          aria-label="Cari siswa"
        />
        {#if query}
          <button
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
            on:click={() => (query = "")}
            aria-label="Bersihkan pencarian"
          >
            ✕
          </button>
        {/if}
      </div>
      <select class="input !w-auto" bind:value={sortBy} aria-label="Urutkan">
        <option value="rank">Urut: Peringkat</option>
        <option value="score">Urut: Skor</option>
        <option value="opc">Urut: OPT</option>
        <option value="name">Urut: Nama</option>
      </select>
    </div>

    {#if displayed.length === 0}
      <div class="card mt-6 grid place-items-center py-12 text-center">
        <p class="muted text-sm">Tidak ada siswa yang cocok dengan pencarianmu.</p>
        <button class="btn-ghost mt-3 !py-1 text-xs" on:click={() => (query = "")}
          >Reset Pencarian</button
        >
      </div>
    {:else}
      <div class="card mt-6 overflow-x-auto !p-0">
        <table class="w-full text-sm">
          <caption class="sr-only">Peringkat siswa</caption>
          <thead class="text-left">
            <tr class="mono-label border-b">
              <th class="px-5 py-3" scope="col">#</th>
              <th class="px-5 py-3" scope="col">Siswa</th>
              <th class="px-5 py-3 text-right" scope="col">Skor</th>
              <th class="px-5 py-3 text-right" scope="col">OPT</th>
            </tr>
          </thead>
          <tbody>
            {#each displayed as e, i (e.user_id)}
              <tr use:reveal={{ delay: i * 15 }} class="border-b last:border-0">
                <td class="px-5 py-3">
                  {#if e.rank <= 3 && sortBy === "rank"}
                    <Icon name="medal" size="14px" class={medalColor[e.rank]} />
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
                <td class="px-5 py-3 text-right">
                  <span
                    class="badge"
                    class:badge-mint={e.score_bp >= 6000}
                    class:badge-neutral={e.score_bp < 6000}
                  >
                    {(e.score_bp / 100).toFixed(1)}%
                  </span>
                </td>
                <td class="px-5 py-3 text-right font-mono">{formatNumber(e.opc_earned)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <Pagination
      {page}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="siswa"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {/if}
</div>
