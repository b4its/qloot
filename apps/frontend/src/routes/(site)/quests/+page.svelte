<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Winner } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { bpToPercent, formatDate, statusLabel } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";

  const PAGE = 20;
  let quests: Quest[] = [];
  let winnersByQuest: Record<string, Winner[]> = {};
  let loading = true;
  let error = "";
  let page = 1;
  let hasMore = false;
  $: canManage = hasRole($auth.user, "teacher");

  async function load() {
    loading = true;
    error = "";
    try {
      quests = await api.get<Quest[]>(`/quests?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = quests.length === PAGE;
      for (const q of quests) {
        if (q.status === "finalized") {
          winnersByQuest[q.id] = await api.get<Winner[]>(`/quests/${q.id}/winners`);
        }
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat quest";
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

  async function finalize(q: Quest) {
    error = "";
    try {
      await api.post(`/quests/${q.id}/finalize`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal finalisasi quest";
    }
  }
  async function publish(q: Quest) {
    error = "";
    try {
      await api.post(`/quests/${q.id}/publish`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mempublikasikan quest";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Quest — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex items-center justify-between">
    <div>
      <p class="mono-label">Gamifikasi</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Quest</h1>
    </div>
    {#if canManage}<a href="/teacher/quests" class="btn-primary">＋ Kelola quest</a>{/if}
  </div>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  {#if loading}
    <p class="mt-6 muted">Memuat quest…</p>
  {:else if quests.length === 0}
    <div class="card mt-6 text-center"><p class="muted">Belum ada quest.</p></div>
  {:else}
    <div class="mt-6 grid gap-4 lg:grid-cols-2">
      {#each quests as q}
        <div class="card lift">
          <div class="flex items-center justify-between">
            <h2 class="font-display text-lg font-bold">{q.title}</h2>
            <span
              class="badge"
              class:badge-mint={q.status === "open"}
              class:badge-indigo={q.status === "finalized"}
              class:badge-neutral={q.status !== "open" && q.status !== "finalized"}
              >{statusLabel(q.status)}</span
            >
          </div>
          <p class="mt-1 text-sm muted">{q.description ?? "Quest cepat untuk peserta teratas."}</p>
          {#if q.rules?.length}
            <ul class="mt-3 space-y-1 text-sm">
              {#each q.rules as r}
                <li class="flex justify-between border-b pb-1 last:border-0">
                  <span>Peringkat {r.rank}</span>
                  <span class="font-mono text-highlight">{r.reward_amount} OPT</span>
                </li>
              {/each}
            </ul>
          {/if}
          {#if q.closes_at}
            <p class="mt-2 text-xs muted">Ditutup {formatDate(q.closes_at)}</p>
          {/if}

          {#if q.status === "finalized" && winnersByQuest[q.id]?.length}
            <div class="mt-3 border-t pt-3">
              <h3 class="hud flex items-center gap-2 font-display font-bold">
                <Icon name="trophy" size="12px" class="text-highlight" /> Pemenang
              </h3>
              <ol class="mt-1 space-y-1 text-sm">
                {#each winnersByQuest[q.id] as w}
                  <li class="flex justify-between">
                    <span>#{w.rank} · <span class="font-mono">{w.user_id.slice(0, 8)}…</span></span>
                    <span>{bpToPercent(w.score_bp)} · {w.reward_amount} OPT</span>
                  </li>
                {/each}
              </ol>
            </div>
          {/if}

          {#if canManage}
            <div class="mt-3 flex gap-2">
              {#if q.status !== "open"}<button class="btn-ghost" on:click={() => publish(q)}
                  >Publikasikan</button
                >{/if}
              {#if q.status !== "finalized"}<button class="btn-primary" on:click={() => finalize(q)}
                  >Finalisasi pemenang</button
                >{/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <Pagination
      {page}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="quest"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {/if}
</div>
