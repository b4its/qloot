<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Winner } from "$lib/types";
  import { bpToPercent, statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let quests: Quest[] = [];
  let winners: Record<string, Winner[]> = {};
  let message = "";
  let error = "";
  let loading = true;
  let busy = "";
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    try {
      quests = await api.get<Quest[]>(`/quests?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = quests.length === PAGE;
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

  async function remove(q: Quest) {
    if (!confirm(`Hapus quest "${q.title}"?`)) return;
    error = "";
    message = "";
    busy = `d-${q.id}`;
    try {
      await api.delete(`/quests/${q.id}`);
      message = "Quest dihapus.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus quest";
    } finally {
      busy = "";
    }
  }

  async function publish(q: Quest) {
    error = "";
    message = "";
    busy = `p-${q.id}`;
    try {
      await api.post<Quest>(`/quests/${q.id}/publish`);
      message = "Quest diterbitkan.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menerbitkan quest";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Quest — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Quest"
    title="Quest"
    subtitle="Beri hadiah pada finisher tercepat yang valid. Pemenang deterministik: skor, lalu kecepatan, lalu attempt id."
    backHref="/teacher"
    backLabel="Panel Guru"
    actionHref="/teacher/quests/new"
    actionLabel="Quest baru"
  />

  <PageAlerts {message} {error} />

  <div class="mt-6 space-y-4">
    {#if loading}
      {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
    {:else if quests.length === 0}
      <div class="card grid place-items-center py-12 text-center">
        <Icon name="trophy" size="26px" class="muted" />
        <p class="mt-3 font-semibold">Belum ada quest</p>
        <p class="text-sm muted">Buat quest pertama untuk memotivasi siswa.</p>
        <a href="/teacher/quests/new" class="btn-primary mt-4">
          <Icon name="plus" size="12px" /> Buat quest
        </a>
      </div>
    {:else}
      {#each quests as q}
        <div class="card">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 class="font-display text-lg font-bold">{q.title}</h2>
              <p class="text-sm muted">Top {q.top_n_winners} · {statusLabel(q.status)}</p>
            </div>
            <div class="flex items-center gap-2">
              {#if q.status === "draft"}
                <button
                  class="btn-secondary"
                  on:click={() => publish(q)}
                  disabled={busy === `p-${q.id}`}
                >
                  {busy === `p-${q.id}` ? "Menerbitkan…" : "Terbitkan"}
                </button>
              {/if}
              {#if q.status !== "finalized"}
                <a href={`/teacher/quests/${q.id}`} class="btn-ghost">
                  <Icon name="pen" size="11px" /> Ubah
                </a>
              {/if}
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
              <button
                class="btn-icon !text-tertiary hover:!border-tertiary"
                on:click={() => remove(q)}
                disabled={q.status === "finalized" || busy === `d-${q.id}`}
                aria-label="Hapus quest"
              >
                <Icon name="trash" size="12px" />
              </button>
            </div>
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
    {/if}
  </div>

  {#if !loading && quests.length > 0}
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
