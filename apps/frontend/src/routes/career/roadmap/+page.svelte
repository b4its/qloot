<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Recommendation, Milestone } from "$lib/types";

  let recs: Recommendation[] = [];
  let milestones: Milestone[] = [];
  let loading = true;
  let busy = false;
  let error = "";
  let message = "";

  async function load() {
    loading = true;
    try {
      recs = await api.get<Recommendation[]>("/career/recommendations");
      milestones = await api.get<Milestone[]>("/career/roadmap");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load analysis";
    } finally {
      loading = false;
    }
  }

  async function generate() {
    busy = true;
    message = "";
    try {
      recs = await api.post<Recommendation[]>("/career/recommendations/generate");
      message = "Draft recommendations generated.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Generation failed";
    } finally {
      busy = false;
    }
  }

  async function submitReview() {
    busy = true;
    try {
      await api.post("/career/recommendations/submit");
      message = "Submitted to the counsellor for review.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Submit failed";
    } finally {
      busy = false;
    }
  }

  async function approve() {
    busy = true;
    try {
      await api.post("/career/recommendations/approve");
      message = "Approved — your roadmap is now active.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Approve failed";
    } finally {
      busy = false;
    }
  }

  async function setProgress(id: string, value: number) {
    await api.patch(`/career/roadmap/${id}`, { progress_percent: value });
    await load();
  }

  $: status = recs.length ? recs[0].status : "none";
  $: top = recs[0];

  onMount(load);
</script>

<svelte:head><title>AI Analysis & Roadmap — QLoot</title></svelte:head>

<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold">AI Analysis & Roadmap</h1>
    <p class="mt-1 text-sm muted">
      Major recommendations from your grades and personality, with a human-in-the-loop approval
      before the roadmap activates.
    </p>
  </div>
  <a href="/career" class="btn-ghost">← Career home</a>
</div>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}
{#if message}
  <p class="mt-4 rounded-lg bg-primary-50 p-3 text-sm dark:bg-slate-800">{message}</p>
{/if}

<div class="mt-4 card">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex items-center gap-3">
      <span
        class="badge"
        class:bg-amber-100={status === "draft"}
        class:text-amber-700={status === "draft"}
        class:bg-sky-100={status === "in_review"}
        class:text-sky-700={status === "in_review"}
        class:bg-green-100={status === "approved"}
        class:text-green-700={status === "approved"}
      >
        {status === "none" ? "no analysis" : status}
      </span>
      <span class="text-xs muted">Human-in-the-loop: counsellor must approve</span>
    </div>
    <div class="flex flex-wrap gap-2">
      <button class="btn-ghost" on:click={generate} disabled={busy}>Generate analysis</button>
      <button
        class="btn-ghost"
        on:click={submitReview}
        disabled={busy || !recs.length || status === "approved"}
      >
        Submit for review
      </button>
      <button
        class="btn-primary"
        on:click={approve}
        disabled={busy || !recs.length || status === "approved"}
      >
        Approve & activate roadmap
      </button>
    </div>
  </div>
</div>

{#if loading}
  <p class="mt-6 muted">Loading…</p>
{:else if !recs.length}
  <div class="card mt-4 text-center">
    <p class="muted">No analysis yet. Add grades and take the Big Five test, then generate.</p>
    <div class="mt-3 flex justify-center gap-2">
      <a href="/dashboard" class="btn-ghost">Add grades</a>
      <a href="/career/personality" class="btn-primary">Take the test</a>
    </div>
  </div>
{:else}
  <div class="mt-4 grid gap-4 lg:grid-cols-3">
    {#each recs as r}
      <div class="card" class:ring-2={r.rank === 1} class:ring-primary-400={r.rank === 1}>
        <div class="flex items-center justify-between">
          <span class="text-xs font-mono uppercase muted">Rank {r.rank}</span>
          <span class="text-lg font-bold text-primary-600">{r.fit_score}%</span>
        </div>
        <h2 class="mt-1 font-semibold">{r.major}</h2>
        <p class="text-xs muted">{r.rationale}</p>
        <div class="mt-3 space-y-2 text-xs">
          <div>
            <div class="flex justify-between">
              <span class="muted">Academic fit</span><span>{r.academic_fit}%</span>
            </div>
            <div class="mt-1 h-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div class="h-full bg-primary-500" style={`width:${r.academic_fit}%`}></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between">
              <span class="muted">Personality fit</span><span>{r.personality_fit}%</span>
            </div>
            <div class="mt-1 h-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div class="h-full bg-primary-500" style={`width:${r.personality_fit}%`}></div>
            </div>
          </div>
        </div>
      </div>
    {/each}
  </div>

  {#if top}
    <div class="card mt-4">
      <h2 class="font-semibold">Top recommendation: {top.major}</h2>
      <div class="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p class="text-xs font-mono uppercase muted">Universities</p>
          <ul class="mt-1 space-y-1 text-sm">
            {#each top.universities ?? [] as u}<li>🎓 {u}</li>{/each}
          </ul>
        </div>
        <div>
          <p class="text-xs font-mono uppercase muted">Admission paths</p>
          <ul class="mt-1 space-y-1 text-sm">
            {#each top.admission_paths ?? [] as p}<li>✅ {p}</li>{/each}
          </ul>
        </div>
        <div>
          <p class="text-xs font-mono uppercase muted">Skills needed</p>
          <ul class="mt-1 space-y-1 text-sm">
            {#each top.skills ?? [] as s}<li>⚡ {s}</li>{/each}
          </ul>
        </div>
        <div>
          <p class="text-xs font-mono uppercase muted">Careers</p>
          <ul class="mt-1 space-y-1 text-sm">
            {#each top.careers ?? [] as c}<li>💼 {c}</li>{/each}
          </ul>
        </div>
      </div>
    </div>
  {/if}

  <div class="card mt-4">
    <h2 class="font-semibold">Milestone roadmap</h2>
    {#if !milestones.length}
      <p class="mt-2 muted">Roadmap activates after counsellor approval.</p>
    {:else}
      <ol class="mt-3 space-y-4">
        {#each milestones as m}
          <li
            class="border-l-2 pl-4"
            class:border-primary-500={m.status === "in_progress"}
            class:border-green-500={m.status === "completed"}
            class:border-slate-200={m.status === "not_started"}
          >
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-xs font-mono uppercase muted">{m.period}</span>
              <span
                class="badge"
                class:bg-primary-100={m.status === "in_progress"}
                class:text-primary-700={m.status === "in_progress"}
                class:bg-green-100={m.status === "completed"}
                class:text-green-700={m.status === "completed"}>{m.status}</span
              >
            </div>
            <p class="font-semibold">{m.title}</p>
            <p class="text-sm muted">{m.description}</p>
            {#if m.tasks}
              <ul class="mt-1 flex flex-wrap gap-3 text-xs muted">
                {#each m.tasks as t}<li>• {t}</li>{/each}
              </ul>
            {/if}
            <div class="mt-2 flex items-center gap-3">
              <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <div class="h-full bg-primary-500" style={`width:${m.progress_percent}%`}></div>
              </div>
              <span class="text-xs font-mono">{m.progress_percent}%</span>
              <button
                class="btn-ghost !py-1 text-xs"
                on:click={() => setProgress(m.id, Math.min(100, m.progress_percent + 25))}
              >
                +25%
              </button>
            </div>
          </li>
        {/each}
      </ol>
    {/if}
  </div>
{/if}
