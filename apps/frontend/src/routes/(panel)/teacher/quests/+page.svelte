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
  import { reveal } from "$lib/actions/reveal";

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
  let query = "";
  let statusFilter: "all" | "draft" | "open" | "closed" | "finalized" = "all";
  let confirmingFinalize: Quest | null = null;

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

  async function executeFinalize(q: Quest) {
    error = "";
    message = "";
    busy = `f-${q.id}`;
    confirmingFinalize = null;
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

  async function loadWinners(q: Quest) {
    if (winners[q.id]) {
      delete winners[q.id];
      winners = { ...winners };
      return;
    }
    try {
      winners[q.id] = await api.get<Winner[]>(`/quests/${q.id}/winners`);
      winners = { ...winners };
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pemenang";
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

  // --- metrics + filtering ---------------------------------------------------
  $: counts = {
    draft: quests.filter((q) => q.status === "draft").length,
    open: quests.filter((q) => q.status === "open" || q.status === "published").length,
    finalized: quests.filter((q) => q.status === "finalized").length,
  };

  $: filtered = quests.filter((q) => {
    if (statusFilter !== "all") {
      if (statusFilter === "open" && q.status !== "open" && q.status !== "published") return false;
      if (statusFilter !== "open" && q.status !== statusFilter) return false;
    }
    if (query.trim() && !q.title.toLowerCase().includes(query.toLowerCase().trim())) return false;
    return true;
  });

  const statusTone: Record<string, string> = {
    draft: "badge-neutral",
    published: "badge-mint",
    open: "badge-mint",
    closed: "badge-amber",
    finalized: "badge-indigo",
  };
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

  {#if loading}
    <div class="mt-6 grid grid-cols-3 gap-3">
      {#each Array(3) as _}<div class="skeleton h-24"></div>{/each}
    </div>
    <div class="mt-6 space-y-4">
      {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
    </div>
  {:else if quests.length === 0}
    <div class="card mt-6 grid place-items-center py-12 text-center">
      <Icon name="trophy" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada quest</p>
      <p class="text-sm muted">Buat quest pertama untuk memotivasi siswa.</p>
      <a href="/teacher/quests/new" class="btn-primary mt-4">
        <Icon name="plus" size="12px" /> Buat quest
      </a>
    </div>
  {:else}
    <!-- Metrics -->
    <div class="mt-6 grid grid-cols-3 gap-3">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total Quest</p>
        <p class="mt-1 font-display text-3xl font-bold">{quests.length}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Aktif</p>
        <p class="mt-1 font-display text-3xl font-bold text-mint" data-role="open-count">
          {counts.open}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Difinalisasi</p>
        <p class="mt-1 font-display text-3xl font-bold text-secondary">{counts.finalized}</p>
      </div>
    </div>

    <!-- Search + status filter -->
    <div class="mt-5 flex flex-wrap items-center gap-2">
      <div class="relative flex-1 min-w-[180px]">
        <Icon
          name="magnifying-glass"
          size="12px"
          class="absolute left-3 top-1/2 -translate-y-1/2 muted"
        />
        <input
          class="input text-xs !py-1.5 !pl-8 w-full"
          placeholder="Cari quest..."
          bind:value={query}
          aria-label="Cari quest"
        />
      </div>
      <div class="flex flex-wrap items-center gap-1 rounded-sm border p-1 surface text-xs">
        {#each [["all", "Semua"], ["draft", "Draf"], ["open", "Aktif"], ["finalized", "Difinalisasi"]] as [val, label]}
          <button
            type="button"
            class="px-2.5 py-1 rounded-xs font-medium transition-colors"
            class:bg-primary={statusFilter === val}
            class:text-[#05060A]={statusFilter === val}
            class:muted={statusFilter !== val}
            on:click={() => (statusFilter = val as typeof statusFilter)}
          >
            {label}
          </button>
        {/each}
      </div>
    </div>

    {#if filtered.length === 0}
      <div class="card mt-6 grid place-items-center py-12 text-center">
        <p class="muted text-sm">Tidak ada quest yang cocok dengan filtermu.</p>
        <button
          class="btn-ghost mt-3 !py-1 text-xs"
          on:click={() => {
            query = "";
            statusFilter = "all";
          }}>Reset Filter</button
        >
      </div>
    {:else}
      <div class="mt-4 space-y-4">
        {#each filtered as q, i (q.id)}
          {@const winnerList = winners[q.id]}
          <div use:reveal={{ delay: i * 20 }} class="card" data-quest={q.id}>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <h2 class="font-display text-lg font-bold">{q.title}</h2>
                  <span class="badge {statusTone[q.status] ?? 'badge-neutral'}">
                    {statusLabel(q.status)}
                  </span>
                  {#if q.status === "finalized"}
                    <span class="badge badge-neutral"
                      ><Icon name="gift" size="9px" /> {q.top_n_winners} pemenang</span
                    >
                  {/if}
                </div>
                <p class="text-sm muted">Top {q.top_n_winners} finisher tercepat</p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                {#if q.status === "draft"}
                  <button
                    class="btn-secondary"
                    on:click={() => publish(q)}
                    disabled={busy === `p-${q.id}`}
                  >
                    <Icon name="upload" size="11px" />
                    {busy === `p-${q.id}` ? "Menerbitkan…" : "Terbitkan"}
                  </button>
                {/if}
                {#if q.status === "finalized"}
                  <button class="btn-ghost" on:click={() => loadWinners(q)}>
                    <Icon name="ranking-star" size="11px" />
                    {winnerList ? "Sembunyikan pemenang" : "Lihat pemenang"}
                  </button>
                {:else}
                  <a href={`/teacher/quests/${q.id}`} class="btn-ghost">
                    <Icon name="pen" size="11px" /> Ubah
                  </a>
                {/if}
                <button
                  class="btn-primary"
                  on:click={() => (confirmingFinalize = q)}
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
            {#if winnerList?.length}
              <ol class="mt-3 space-y-1 border-t pt-3 text-sm">
                {#each winnerList as w}
                  <li class="flex justify-between">
                    <span class="flex items-center gap-2">
                      <span class="badge badge-amber">#{w.rank}</span>
                      <span class="font-mono">{w.user_id.slice(0, 8)}…</span>
                    </span>
                    <span class="mono-label">{bpToPercent(w.score_bp)} · {w.reward_amount} OPT</span
                    >
                  </li>
                {/each}
              </ol>
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
  {/if}
</div>

<!-- Finalization confirmation modal -->
{#if confirmingFinalize}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xs">
    <div class="card w-full max-w-md space-y-4 border-amber-500/40 shadow-2xl">
      <div class="flex items-center gap-2 text-amber-400">
        <Icon name="triangle-exclamation" size="18px" />
        <h3 class="font-display text-lg font-bold">Konfirmasi Finalisasi Quest</h3>
      </div>
      <p class="text-xs text-foreground/90 leading-relaxed">
        Apakah Anda yakin ingin memfinalisasi pemenang untuk quest <strong
          >"{confirmingFinalize.title}"</strong
        >?
      </p>
      <p class="text-xs muted leading-relaxed">
        Pemenang ditentukan deterministik dari skor tertinggi dan waktu submit tercepat. Hadiah
        token OPT akan dialokasikan ke akun pemenang. Tindakan ini tidak dapat dibatalkan.
      </p>
      <div class="flex items-center justify-end gap-2 border-t pt-3">
        <button class="btn-ghost text-xs" on:click={() => (confirmingFinalize = null)}>Batal</button
        >
        <button
          class="btn-primary !bg-amber-500 !text-black text-xs font-semibold"
          on:click={() => confirmingFinalize && executeFinalize(confirmingFinalize)}
          data-role="confirm-finalize"
        >
          Ya, Finalisasi Pemenang
        </button>
      </div>
    </div>
  </div>
{/if}
