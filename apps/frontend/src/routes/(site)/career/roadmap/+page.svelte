<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Recommendation, Milestone, PendingReview } from "$lib/types";
  import { statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";

  let recs: Recommendation[] = [];
  let milestones: Milestone[] = [];
  let pending: PendingReview[] = [];
  let loading = true;
  let busy = false;
  let approvingId = "";
  let error = "";
  let message = "";

  // Only a counselor (teacher/admin) may approve the human-in-the-loop review;
  // a student can create, submit, and view — never approve their own plan.
  $: isCounselor = hasRole($auth.user, "teacher") || hasRole($auth.user, "admin");

  async function load() {
    loading = true;
    try {
      recs = await api.get<Recommendation[]>("/career/recommendations");
      milestones = await api.get<Milestone[]>("/career/roadmap");
      if (isCounselor) {
        pending = await api.get<PendingReview[]>("/career/recommendations/pending");
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat analisis";
    } finally {
      loading = false;
    }
  }

  async function generate() {
    busy = true;
    message = "";
    try {
      recs = await api.post<Recommendation[]>("/career/recommendations/generate");
      message = "Rekomendasi draf berhasil dibuat.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat rekomendasi";
    } finally {
      busy = false;
    }
  }

  async function submitReview() {
    busy = true;
    try {
      await api.post("/career/recommendations/submit");
      message = "Dikirim ke pembimbing untuk ditinjau.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim";
    } finally {
      busy = false;
    }
  }

  async function approve() {
    busy = true;
    try {
      await api.post("/career/recommendations/approve");
      message = "Disetujui — peta jalanmu kini aktif.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyetujui";
    } finally {
      busy = false;
    }
  }

  /** Counselor: approve a specific student's plan by id. */
  async function approveStudent(p: PendingReview) {
    if (approvingId) return;
    approvingId = p.user_id;
    error = "";
    message = "";
    try {
      await api.post(`/career/recommendations/approve?user_id=${p.user_id}`);
      message = `Peta jalan ${p.display_name} disetujui.`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyetujui";
    } finally {
      approvingId = "";
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

<svelte:head><title>Analisis AI & Peta Jalan — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Analisis</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Analisis AI & Peta Jalan</h1>
      <p class="mt-1 text-sm muted">
        Rekomendasi jurusan dari nilai dan kepribadianmu, dengan persetujuan pembimbing
        (human-in-the-loop) sebelum roadmap aktif.
      </p>
    </div>
    <a href="/career" class="btn-ghost">← Beranda karier</a>
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
          {status === "none" ? "belum ada analisis" : statusLabel(status)}
        </span>
        <span class="text-xs muted">Human-in-the-loop: pembimbing harus menyetujui</span>
      </div>
      <div class="flex flex-wrap gap-2">
        <button class="btn-ghost" on:click={generate} disabled={busy}>Buat analisis</button>
        <button
          class="btn-ghost"
          on:click={submitReview}
          disabled={busy || !recs.length || status === "approved"}
        >
          Kirim untuk ditinjau
        </button>
        {#if isCounselor}
          <button
            class="btn-primary"
            on:click={approve}
            disabled={busy || !recs.length || status === "approved"}
          >
            Setujui & aktifkan peta jalan
          </button>
        {/if}
      </div>
    </div>
  </div>

  {#if isCounselor}
    <div class="card mt-4">
      <div class="flex items-center justify-between">
        <h2 class="font-display font-bold">Menunggu persetujuan</h2>
        <span class="badge badge-neutral">{pending.length}</span>
      </div>
      <p class="mt-1 text-xs muted">
        Peta jalan siswa yang dikirim untuk ditinjau. Setujui untuk mengaktifkannya.
      </p>
      {#if pending.length}
        <ul class="mt-3 space-y-2 text-sm">
          {#each pending as p (p.user_id)}
            <li class="flex items-center justify-between gap-3 border-b pb-2 last:border-0">
              <span>
                <span class="font-medium">{p.display_name}</span>
                <span class="text-xs muted"> · {p.top_major} · {p.count} rekomendasi</span>
              </span>
              <button
                class="btn-primary !py-1.5 flex-none"
                on:click={() => approveStudent(p)}
                disabled={approvingId === p.user_id}
              >
                {approvingId === p.user_id ? "Memproses…" : "Setujui"}
              </button>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="mt-2 muted text-sm">Tidak ada yang menunggu persetujuan.</p>
      {/if}
    </div>
  {/if}

  {#if loading}
    <p class="mt-6 muted">Memuat …</p>
  {:else if !recs.length}
    <div class="card mt-4 text-center">
      <p class="muted">
        Belum ada analisis. Tambahkan nilai dan ikuti tes Big Five, lalu buat analisis.
      </p>
      <div class="mt-3 flex justify-center gap-2">
        <a href="/dashboard" class="btn-ghost">Tambah nilai</a>
        <a href="/career/personality" class="btn-primary">Ikuti tes</a>
      </div>
    </div>
  {:else}
    <div class="mt-4 grid gap-4 lg:grid-cols-3">
      {#each recs as r}
        <div class="card" class:border-primary={r.rank === 1}>
          <div class="flex items-center justify-between">
            <span class="mono-label">Peringkat {r.rank}</span>
            <span class="text-lg font-bold text-primary">{r.fit_score}%</span>
          </div>
          <h2 class="mt-1 font-display text-base font-bold">{r.major}</h2>
          <p class="text-xs muted">{r.rationale}</p>
          <div class="mt-3 space-y-2 text-xs">
            <div>
              <div class="flex justify-between">
                <span class="muted">Kecocokan akademik</span><span>{r.academic_fit}%</span>
              </div>
              <div class="track mt-1 h-1">
                <span style={`width:${r.academic_fit}%`}></span>
              </div>
            </div>
            <div>
              <div class="flex justify-between">
                <span class="muted">Kecocokan kepribadian</span><span>{r.personality_fit}%</span>
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
        <h2 class="hud font-display text-lg font-bold">Rekomendasi teratas: {top.major}</h2>
        <div class="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p class="mono-label">Universitas</p>
            <ul class="mt-1 space-y-1 text-sm">
              {#each top.universities ?? [] as u}<li class="flex items-center gap-2">
                  <Icon name="graduation-cap" size="11px" class="text-primary" />
                  {u}
                </li>{/each}
            </ul>
          </div>
          <div>
            <p class="mono-label">Jalur masuk</p>
            <ul class="mt-1 space-y-1 text-sm">
              {#each top.admission_paths ?? [] as p}<li class="flex items-center gap-2">
                  <Icon name="circle-check" size="11px" class="text-secondary" />
                  {p}
                </li>{/each}
            </ul>
          </div>
          <div>
            <p class="mono-label">Keterampilan yang dibutuhkan</p>
            <ul class="mt-1 space-y-1 text-sm">
              {#each top.skills ?? [] as s}<li class="flex items-center gap-2">
                  <Icon name="bolt" size="11px" class="text-highlight" />
                  {s}
                </li>{/each}
            </ul>
          </div>
          <div>
            <p class="mono-label">Karier</p>
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
      <h2 class="hud font-display text-lg font-bold">Peta jalan tonggak</h2>
      {#if !milestones.length}
        <p class="mt-2 muted">Peta jalan aktif setelah disetujui pembimbing.</p>
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
                  class:badge-neutral={m.status === "not_started"}>{statusLabel(m.status)}</span
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
