<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Exam, Winner } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";
  import { statusLabel } from "$lib/utils/format";

  let quests: Quest[] = [];
  let exams: Exam[] = [];
  let winners: Record<string, Winner[]> = {};
  let newQuest = { title: "", exam_id: "", top_n_winners: 3, ranks: [100, 60, 40] };
  let message = "";
  let error = "";
  let loading = true;
  let busy = "";

  async function load() {
    loading = true;
    try {
      quests = await api.get<Quest[]>("/quests");
      exams = await api.get<Exam[]>("/exams");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat quest";
    } finally {
      loading = false;
    }
  }

  async function create() {
    error = "";
    message = "";
    busy = "create";
    try {
      const rules = newQuest.ranks.map((amount, i) => ({ rank: i + 1, reward_amount: amount }));
      await api.post<Quest>("/quests", {
        title: newQuest.title,
        exam_id: newQuest.exam_id || null,
        top_n_winners: newQuest.top_n_winners,
        rules,
      });
      message = "Quest dibuat.";
      newQuest.title = "";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat quest";
    } finally {
      busy = "";
    }
  }

  async function finalize(q: Quest) {
    error = "";
    message = "";
    busy = `f-${q.id}`;
    try {
      const res = await api.post<{ allocations_created: number }>(`/quests/${q.id}/finalize`);
      message = `Difinalisasi — ${res.allocations_created} hadiah dialokasikan`;
      winners[q.id] = await api.get<Winner[]>(`/quests/${q.id}/winners`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal finalisasi quest";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Quest (Guru) — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <p class="mono-label">Panel Guru · Quest</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Kelola Quest</h1>
  <p class="mt-1 muted">
    Beri hadiah pada finisher tercepat yang valid. Pemenang bersifat deterministik: skor, lalu
    kecepatan, lalu attempt id.
  </p>

  {#if message}<p class="alert-ok mt-4">
      {message}
    </p>{/if}
  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  <div class="card mt-6">
    <h2 class="hud font-display text-lg font-bold">Quest baru</h2>
    <div class="mt-3 grid gap-3 sm:grid-cols-2">
      <input class="input" placeholder="Judul" bind:value={newQuest.title} />
      <select class="input" bind:value={newQuest.exam_id}>
        <option value="">Tanpa ujian tertaut</option>
        {#each exams as e}<option value={e.id}>{e.title}</option>{/each}
      </select>
      <input class="input" type="number" min="1" max="50" bind:value={newQuest.top_n_winners} />
      <div class="flex items-center gap-2">
        {#each newQuest.ranks as amount, i}
          <input class="input w-20" type="number" min="0" bind:value={newQuest.ranks[i]} />
        {/each}
        <span class="text-xs muted">OPC per peringkat</span>
      </div>
    </div>
    <button
      class="btn-primary mt-3"
      on:click={create}
      disabled={newQuest.title.length < 2 || busy === "create"}
      >{busy === "create" ? "Membuat…" : "Buat quest"}</button
    >
  </div>

  <div class="mt-6 space-y-4">
    {#if loading}
      {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
    {:else}
      {#each quests as q}
        <div class="card">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 class="font-display text-lg font-bold">{q.title}</h2>
              <p class="text-sm muted">Top {q.top_n_winners} · {statusLabel(q.status)}</p>
            </div>
            <button
              class="btn-primary"
              on:click={() => finalize(q)}
              disabled={q.status === "finalized" || busy === `f-${q.id}`}
            >
              {busy === `f-${q.id}`
                ? "Memproses…"
                : q.status === "finalized"
                  ? "Final"
                  : "Finalisasi pemenang"}
            </button>
          </div>
          {#if winners[q.id]?.length}
            <ol class="mt-2 space-y-1 text-sm">
              {#each winners[q.id] as w}
                <li class="flex justify-between border-b pb-1 last:border-0">
                  <span>#{w.rank} · <span class="font-mono">{w.user_id.slice(0, 8)}…</span></span>
                  <span>{bpToPercent(w.score_bp)} · {w.reward_amount} OPC</span>
                </li>
              {/each}
            </ol>
          {/if}
        </div>
      {/each}
      {#if quests.length === 0}<p class="muted">Belum ada quest.</p>{/if}
    {/if}
  </div>
</div>
