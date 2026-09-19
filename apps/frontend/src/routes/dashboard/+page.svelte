<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { AcademicDashboard, GradeRow } from "$lib/types";

  let data: AcademicDashboard | null = null;
  let grades: GradeRow[] = [];
  let loading = true;
  let error = "";
  let form = { subject: "Fisika", grade: 85 };
  let saving = false;

  const subjects = ["Fisika", "Matematika", "Kimia", "Biologi", "B. Inggris", "B. Indonesia"];

  async function load() {
    loading = true;
    try {
      data = await api.get<AcademicDashboard>("/career/dashboard");
      grades = await api.get<GradeRow[]>("/career/grades");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load dashboard";
    } finally {
      loading = false;
    }
  }

  async function addGrade() {
    saving = true;
    try {
      await api.post("/career/grades", form);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Could not save grade";
    } finally {
      saving = false;
    }
  }

  // Radar geometry (hexagon, 6 dimensions).
  function radarPoints(values: number[], cx = 150, cy = 140, r = 110): string {
    return values
      .map((v, i) => {
        const angle = (Math.PI / 3) * i - Math.PI / 2;
        const rr = (v / 100) * r;
        return `${cx + rr * Math.cos(angle)},${cy + rr * Math.sin(angle)}`;
      })
      .join(" ");
  }

  function axis(i: number, len: number, cx = 150, cy = 140, r = 110) {
    const angle = (Math.PI / 3) * i - Math.PI / 2;
    return {
      x: cx + r * Math.cos(angle) * len,
      y: cy + r * Math.sin(angle) * len,
      lx: cx + (r + 18) * Math.cos(angle),
      ly: cy + (r + 18) * Math.sin(angle),
    };
  }

  $: radarValues = data?.radar?.map((d) => d.value) ?? [];
  $: trendPts = (data?.trend ?? [])
    .map((t, i) => {
      const x = 10 + i * (460 / Math.max(1, (data?.trend.length ?? 1) - 1));
      const y = 160 - (t.value / 100) * 140;
      return `${x},${y}`;
    })
    .join(" ");

  onMount(load);
</script>

<svelte:head><title>Academic Dashboard — QLoot</title></svelte:head>

<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold">Academic Dashboard</h1>
    <p class="mt-1 text-sm muted">Your performance summary — simulated from recorded grades.</p>
  </div>
  <a href="/career" class="btn-ghost">← Career home</a>
</div>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading…</p>
{:else if data}
  <div class="mt-4 grid gap-4 sm:grid-cols-3">
    <div class="card">
      <div class="text-sm muted">Average grade</div>
      <div class="text-3xl font-bold text-primary-600">{data.average}</div>
      <div class="text-xs muted">across recorded subjects</div>
    </div>
    <div class="card">
      <div class="text-sm muted">Strongest subject</div>
      <div class="text-2xl font-bold">{data.strong_subject ?? "—"}</div>
    </div>
    <div class="card">
      <div class="text-sm muted">Needs attention</div>
      <div class="text-2xl font-bold text-amber-500">{data.weak_subject ?? "—"}</div>
    </div>
  </div>

  <div class="mt-4 grid gap-4 lg:grid-cols-5">
    <div class="card lg:col-span-2">
      <h2 class="font-semibold">Interest map</h2>
      <p class="text-xs muted">Interest spread across 6 study areas</p>
      {#if radarValues.length}
        <svg
          viewBox="0 0 300 300"
          class="mx-auto mt-2 h-64 w-full"
          role="img"
          aria-label="Interest radar"
        >
          <g stroke="currentColor" class="opacity-20" fill="none">
            {#each [1, 0.66, 0.33] as f}
              <polygon points={radarPoints(radarValues.map(() => f * 100))} />
            {/each}
            {#each [0, 1, 2, 3, 4, 5] as i}
              <line x1="150" y1="140" x2={axis(i, 1).x} y2={axis(i, 1).y} />
            {/each}
          </g>
          <polygon
            points={radarPoints(radarValues)}
            fill="rgb(37 99 235 / 0.18)"
            stroke="rgb(37 99 235)"
            stroke-width="2"
          />
          {#each data.radar as d, i}
            <text
              x={axis(i, 1).lx}
              y={axis(i, 1).ly}
              text-anchor="middle"
              font-size="10"
              fill="currentColor"
              class="opacity-70"
            >
              {d.dimension}
            </text>
          {/each}
        </svg>
      {:else}
        <p class="mt-2 muted">Add grades to see your interest map.</p>
      {/if}
    </div>

    <div class="card lg:col-span-3">
      <h2 class="font-semibold">Grade trend</h2>
      <p class="text-xs muted">Simulated 6-month trajectory</p>
      {#if data.trend.length}
        <svg viewBox="0 0 480 180" class="mt-2 h-48 w-full" role="img" aria-label="Grade trend">
          <g stroke="currentColor" class="opacity-10">
            {#each [20, 60, 100, 140] as y}<line x1="0" y1={y} x2="480" y2={y} />{/each}
          </g>
          <polyline
            points={trendPts}
            fill="none"
            stroke="rgb(37 99 235)"
            stroke-width="2.5"
            stroke-linejoin="round"
          />
          {#each data.trend as t, i}
            {@const x = 10 + i * (460 / Math.max(1, data.trend.length - 1))}
            {@const y = 160 - (t.value / 100) * 140}
            <circle cx={x} cy={y} r="3.5" fill="rgb(37 99 235)" />
            <text
              {x}
              y="176"
              text-anchor="middle"
              font-size="10"
              fill="currentColor"
              class="opacity-60">{t.month}</text
            >
          {/each}
        </svg>
      {:else}
        <p class="mt-2 muted">No trend data yet.</p>
      {/if}
    </div>
  </div>

  <div class="card mt-4">
    <h2 class="font-semibold">AI insights</h2>
    <div class="mt-3 grid gap-3 sm:grid-cols-3">
      {#each data.insights as ins}
        <div class="rounded-xl border p-4">
          <div class="text-xs font-mono uppercase muted">{ins.kind}</div>
          <p class="mt-1 text-sm font-semibold">{ins.title}</p>
          <p class="text-xs muted">{ins.detail}</p>
        </div>
      {/each}
    </div>
  </div>

  <div class="mt-4 grid gap-4 lg:grid-cols-3">
    <div class="card lg:col-span-2">
      <h2 class="font-semibold">Grades per subject</h2>
      <div class="mt-3 space-y-2">
        {#each data.subjects as s}
          <div class="flex items-center gap-3">
            <span class="w-24 text-sm">{s.subject}</span>
            <div class="h-2 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div class="h-full rounded-full bg-primary-500" style={`width:${s.grade}%`}></div>
            </div>
            <span class="w-8 text-right text-sm">{s.grade}</span>
          </div>
        {/each}
      </div>
    </div>

    <div class="card">
      <h2 class="font-semibold">Add / update a grade</h2>
      <div class="mt-3 space-y-3">
        <select class="input" bind:value={form.subject}>
          {#each subjects as s}<option value={s}>{s}</option>{/each}
        </select>
        <input class="input" type="number" min="0" max="100" bind:value={form.grade} />
        <button class="btn-primary w-full" on:click={addGrade} disabled={saving}>
          {saving ? "Saving…" : "Save grade"}
        </button>
        <p class="text-xs muted">Recorded subjects: {grades.length}</p>
      </div>
    </div>
  </div>
{/if}
