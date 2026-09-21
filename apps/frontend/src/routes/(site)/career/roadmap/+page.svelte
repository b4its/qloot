<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
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
    error = "";
    try {
      await api.patch(`/career/roadmap/${id}`, { progress_percent: value });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui progres";
    }
  }

  $: status = recs.length ? recs[0].status : "none";
  $: top = recs[0];

  onMount(load);
</script>

<svelte:head><title>AI Analysis & Roadmap — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Analisis</p>
      <h1 class="mt-2 font-display text-3xl font-bold">AI Analysis & Roadmap</h1>
      <p class="mt-1 text-sm muted">
        Rekomendasi jurusan dari nilai dan kepribadianmu, dengan persetujuan pembimbing
        (human-in-the-loop) sebelum roadmap aktif.
      </p>
    </div>
    <a href="/career" class="btn-ghost">← Career home</a>
  </div>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}
  {#if message}
    <p class="alert-ok mt-4">{message}</p>
  {/if}

  <div class="mt-6 card">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <span
          class="badge"
          class:badge-amber={status === "draft"}
          class:badge-indigo={status === "in_review"}
          class:badge-mint={status === "approved"}
          class:badge-neutral={status === "none"}
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
        <div class="card" class:border-primary={r.rank === 1}>
          <div class="flex items-center justify-between">
            <span class="mono-label">Rank {r.rank}</span>
            <span class="text-lg font-bold text-primary">{r.fit_score}%</span>
          </div>
          <h2 class="mt-1 font-display text-base font-bold">{r.major}</h2>
          <p class="text-xs muted">{r.rationale}</p>
          <div class="mt-3 space-y-2 text-xs">
            <div>
              <div class="flex justify-between">
                <span class="muted">Academic fit</span><span>{r.academic_fit}%</span>
              </div>
              <div class="track mt-1 h-1">
                <span style={`width:${r.academic_fit}%`}></span>
              </div>
            </div>
            <div>
              <div class="flex justify-between">
                <span class="muted">Personality fit</span><span>{r.personality_fit}%</span>
              </div>
              <div class="track mt-1 h-1">
                <span style={`width:${r.personality_fit}%`}></span>
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>

    {#if top}
      <div class="card mt-4">
        <h2 class="hud font-display text-lg font-bold">Top recommendation: {top.major}</h2>
        <div class="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p class="mono-label">Universities</p>
            <ul class="mt-1 space-y-1 text-sm">
              {#each top.universities ?? [] as u}<li class="flex items-center gap-2">
                  <Icon name="graduation-cap" size="11px" class="text-primary" />
                  {u}
                </li>{/each}
            </ul>
          </div>
          <div>
            <p class="mono-label">Admission paths</p>
            <ul class="mt-1 space-y-1 text-sm">
              {#each top.admission_paths ?? [] as p}<li class="flex items-center gap-2">
                  <Icon name="circle-check" size="11px" class="text-secondary" />
                  {p}
                </li>{/each}
            </ul>
          </div>
          <div>
            <p class="mono-label">Skills needed</p>
            <ul class="mt-1 space-y-1 text-sm">
              {#each top.skills ?? [] as s}<li class="flex items-center gap-2">
                  <Icon name="bolt" size="11px" class="text-highlight" />
                  {s}
                </li>{/each}
            </ul>
          </div>
          <div>
            <p class="mono-label">Careers</p>
            <ul class="mt-1 space-y-1 text-sm">
              {#each top.careers ?? [] as c}<li class="flex items-center gap-2">
                  <Icon name="briefcase" size="11px" class="text-primary" />
                  {c}
                </li>{/each}
            </ul>
          </div>
        </div>
      </div>
    {/if}

    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Milestone roadmap</h2>
      {#if !milestones.length}
        <p class="mt-2 muted">Roadmap activates after counsellor approval.</p>
      {:else}
        <ol class="mt-3 space-y-4">
          {#each milestones as m}
            <li
              class="border-l-2 pl-4"
              class:border-primary={m.status === "in_progress"}
              class:border-secondary={m.status === "completed"}
              class:border-line={m.status === "not_started"}
            >
              <div class="flex flex-wrap items-center gap-2">
                <span class="mono-label">{m.period}</span>
                <span
                  class="badge"
                  class:badge-indigo={m.status === "in_progress"}
                  class:badge-mint={m.status === "completed"}
                  class:badge-neutral={m.status === "not_started"}>{m.status}</span
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
                <div class="track h-1.5 flex-1">
                  <span style={`width:${m.progress_percent}%`}></span>
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
</div>
