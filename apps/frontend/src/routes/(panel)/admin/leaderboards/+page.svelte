<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { bpToPercent, formatDate } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

  interface SnapshotRow {
    id: string;
    scope: string;
    scope_id: string | null;
    period: string;
    is_materialized: boolean;
    updated_at: string;
  }

  interface EntryRow {
    user_id: string;
    rank: number;
    score_bp: number;
    display_name?: string;
    name?: string;
  }

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  let snapshots: SnapshotRow[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let refreshing = "";
  // Entries of the snapshot currently opened (GET /rankings/leaderboards/{id}/entries).
  let openId = "";
  let entries: EntryRow[] = [];

  let scopeId = "";
  let scopeFilter = "all";
  let query = "";
  // A refresh materializes a snapshot (a write); confirm it.
  let confirmingRefresh: { scope: "global" | "room" | "quest"; id?: string } | null = null;

  async function load() {
    if (!hasRole($auth.user, "admin")) return;
    loading = true;
    error = "";
    try {
      snapshots = await api.get<SnapshotRow[]>("/rankings/leaderboards?limit=200");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat papan peringkat";
    } finally {
      loading = false;
    }
  }

  async function openEntries(id: string) {
    // Re-clicking the open snapshot closes it.
    if (openId === id) {
      openId = "";
      return;
    }
    openId = id;
    entries = [];
    entriesError = "";
    entriesLoading = true;
    try {
      const detail = await api.get<{ entries: EntryRow[] }>(`/rankings/leaderboards/${id}/entries`);
      entries = detail.entries ?? [];
    } catch (e) {
      // Keep a distinct error so a failed fetch is never shown as "no entries".
      entriesError = e instanceof ApiError ? e.message : "Gagal memuat entri";
    } finally {
      entriesLoading = false;
    }
  }
  let entriesError = "";
  let entriesLoading = false;

  /** Reload the currently open snapshot's entries after a failure. */
  async function retryEntries() {
    const id = openId;
    if (!id) return;
    entriesError = "";
    entriesLoading = true;
    try {
      const detail = await api.get<{ entries: EntryRow[] }>(`/rankings/leaderboards/${id}/entries`);
      entries = detail.entries ?? [];
    } catch (e) {
      entriesError = e instanceof ApiError ? e.message : "Gagal memuat entri";
    } finally {
      entriesLoading = false;
    }
  }

  async function refresh(scope: "global" | "room" | "quest", id?: string) {
    error = "";
    message = "";
    confirmingRefresh = null;
    refreshing = scope + (id ?? "");
    try {
      const qs = id ? `scope=${scope}&scope_id=${id}` : `scope=${scope}`;
      const res = await api.post<{ materialized: number }>(`/rankings/leaderboards/refresh?${qs}`);
      message = `Papan ${scope} diperbarui: ${res.materialized} entri.`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui papan peringkat";
    } finally {
      refreshing = "";
    }
  }

  onMount(load);

  // --- metrics + filtering ---------------------------------------------------
  $: scopeCounts = snapshots.reduce<Record<string, number>>((acc, s) => {
    acc[s.scope] = (acc[s.scope] ?? 0) + 1;
    return acc;
  }, {});
  $: materializedCount = snapshots.filter((s) => s.is_materialized).length;

  $: filteredSnapshots = snapshots.filter((s) => {
    if (scopeFilter !== "all" && s.scope !== scopeFilter) return false;
    if (query.trim()) {
      const q = query.toLowerCase().trim();
      const hay = `${s.scope} ${s.scope_id ?? ""} ${s.period}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
</script>

<svelte:head><title>Papan Peringkat | QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Papan Peringkat"
    title="Papan Peringkat Termaterialisasi"
    subtitle="Snapshot peringkat global, ruang, dan quest (bertahan meski nilai diedit belakangan)."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  <!-- Metrics -->
  {#if !loading && snapshots.length > 0}
    <div class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Snapshot</p>
        <p class="mt-1 font-display text-3xl font-bold" data-role="snapshot-count">
          {snapshots.length}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Termaterialisasi</p>
        <p class="mt-1 font-display text-3xl font-bold text-mint">{materializedCount}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Global</p>
        <p class="mt-1 font-display text-3xl font-bold">{scopeCounts["global"] ?? 0}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Ruang / quest</p>
        <p class="mt-1 font-display text-3xl font-bold text-primary">
          {(scopeCounts["room"] ?? 0) + (scopeCounts["quest"] ?? 0)}
        </p>
      </div>
    </div>
  {/if}

  <div class="card mt-4">
    <h2 class="hud font-display text-lg font-bold">Perbarui manual</h2>
    <p class="text-xs muted mt-1">
      Materialisasi ulang snapshot dari data peringkat terkini (tercatat di audit log).
    </p>
    <div class="mt-3 flex flex-wrap items-end gap-2">
      <button
        class="btn-primary"
        on:click={() => (confirmingRefresh = { scope: "global" })}
        disabled={refreshing === "global"}
      >
        {refreshing === "global" ? "Memproses…" : "Perbarui papan global"}
      </button>
      <label class="block">
        <span class="mono-label">ID ruang/quest</span>
        <input class="input mt-1" placeholder="uuid" bind:value={scopeId} />
      </label>
      <button
        class="btn-secondary"
        on:click={() => (confirmingRefresh = { scope: "room", id: scopeId })}
        disabled={!scopeId || refreshing === "room" + scopeId}
      >
        Perbarui ruang
      </button>
      <button
        class="btn-secondary"
        on:click={() => (confirmingRefresh = { scope: "quest", id: scopeId })}
        disabled={!scopeId || refreshing === "quest" + scopeId}
      >
        Perbarui quest
      </button>
    </div>
  </div>

  <div class="card mt-6 overflow-x-auto">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="mono-label">Snapshot yang ada</p>
      {#if !loading && snapshots.length > 0}
        <div class="flex flex-wrap items-center gap-2">
          <select
            class="input text-xs !py-1 w-auto"
            bind:value={scopeFilter}
            aria-label="Filter cakupan"
          >
            <option value="all">Semua cakupan</option>
            <option value="global">Global</option>
            <option value="room">Ruang</option>
            <option value="quest">Quest</option>
          </select>
          <input
            class="input text-xs !py-1 w-48"
            placeholder="Cari ID/periode…"
            bind:value={query}
            aria-label="Cari snapshot"
          />
        </div>
      {/if}
    </div>
    {#if loading}
      <div class="skeleton h-8 mt-3"></div>
    {:else if snapshots.length === 0}
      <p class="py-2 muted mt-3">Belum ada papan peringkat yang dimaterialisasi.</p>
    {:else if filteredSnapshots.length === 0}
      <p class="py-2 muted mt-3">Tidak ada snapshot yang cocok dengan filtermu.</p>
    {:else}
      <table class="w-full text-sm mt-3">
        <caption class="sr-only">Snapshot papan peringkat</caption>
        <thead class="text-left muted">
          <tr>
            <th class="py-1" scope="col">Cakupan</th>
            <th scope="col">ID</th>
            <th scope="col">Periode</th>
            <th scope="col">Diperbarui</th>
            <th scope="col"></th>
          </tr>
        </thead>
        <tbody>
          {#each filteredSnapshots as s (s.id)}
            <tr class="border-t">
              <td class="py-1">
                <span
                  class="badge"
                  class:badge-indigo={s.scope === "global"}
                  class:badge-mint={s.scope === "room"}
                  class:badge-amber={s.scope === "quest"}>{s.scope}</span
                >
              </td>
              <td class="font-mono text-xs">{s.scope_id?.slice(0, 8) ?? "-"}</td>
              <td>{s.period}</td>
              <td class="text-xs muted">{formatDate(s.updated_at)}</td>
              <td class="text-right">
                <button class="btn-ghost !py-1 text-xs" on:click={() => openEntries(s.id)}
                  >{openId === s.id ? "Tutup" : "Lihat entri"}</button
                >
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    {#if openId}
      <div class="mt-4 border-t pt-4">
        <div class="flex items-center justify-between">
          <p class="mono-label">Entri snapshot</p>
          <button class="btn-ghost !py-1 text-xs" on:click={() => (openId = "")}>Tutup</button>
        </div>
        {#if entriesLoading}
          <div class="mt-2 space-y-2">
            {#each Array(3) as _}<div class="skeleton h-8"></div>{/each}
          </div>
        {:else if entriesError}
          <div class="mt-2 space-y-2" role="alert" aria-live="assertive">
            <p class="text-sm text-danger">{entriesError}</p>
            <button class="btn-ghost !py-1 text-xs" on:click={retryEntries}>Coba lagi</button>
          </div>
        {:else if entries.length === 0}
          <p class="mt-2 muted text-sm">Tidak ada entri.</p>
        {:else}
          <ol class="mt-2 space-y-1 text-sm">
            {#each entries as e (e.user_id)}
              <li class="flex items-center justify-between border-b py-1 last:border-0">
                <span>
                  <span class="font-mono text-xs">#{e.rank}</span>
                  {e.display_name ?? e.name ?? e.user_id.slice(0, 8)}
                </span>
                <span class="font-mono text-xs">{bpToPercent(e.score_bp)}</span>
              </li>
            {/each}
          </ol>
        {/if}
      </div>
    {/if}
  </div>
</div>

<!-- Refresh confirmation modal -->
{#if confirmingRefresh}
  <ConfirmDialog
    title="Materialisasi Ulang Snapshot"
    description={`Perbarui papan peringkat ${confirmingRefresh.scope}${confirmingRefresh.id ? ` untuk ${confirmingRefresh.id.slice(0, 8)}…` : ""}?`}
    hint="Snapshot akan dihitung ulang dari data terkini dan menggantikan entri yang ada. Tindakan ini tercatat di audit log."
    confirmLabel="Ya, Perbarui"
    confirmRole="confirm-refresh"
    busy={refreshing !== ""}
    onConfirm={() => confirmingRefresh && refresh(confirmingRefresh.scope, confirmingRefresh.id)}
    close={() => (confirmingRefresh = null)}
  />
{/if}
