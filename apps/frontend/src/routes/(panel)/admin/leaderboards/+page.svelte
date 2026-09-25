<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatDate } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

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

  async function load() {
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
    openId = id;
    entries = [];
    try {
      const detail = await api.get<{ entries: EntryRow[] }>(`/rankings/leaderboards/${id}/entries`);
      entries = detail.entries ?? [];
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat entri";
    }
  }

  async function refresh(scope: "global" | "room" | "quest", id?: string) {
    error = "";
    message = "";
    refreshing = scope + (id ?? "");
    try {
      const qs = id ? `scope=${scope}&scope_id=${id}` : `scope=${scope}`;
      const res = await api.post<{ materialized: number }>(`/rankings/leaderboards/refresh?${qs}`);
      message = `Papan ${scope} diperbarui — ${res.materialized} entri.`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui papan peringkat";
    } finally {
      refreshing = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Papan Peringkat — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Papan Peringkat"
    title="Papan Peringkat Termaterialisasi"
    subtitle="Snapshot peringkat global, ruang, dan quest — bertahan meski nilai diedit belakangan."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  <div class="card mt-4">
    <h2 class="hud font-display text-lg font-bold">Perbarui manual</h2>
    <div class="mt-3 flex flex-wrap items-end gap-2">
      <button
        class="btn-primary"
        on:click={() => refresh("global")}
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
        on:click={() => refresh("room", scopeId)}
        disabled={!scopeId || refreshing === "room" + scopeId}
      >
        Perbarui ruang
      </button>
      <button
        class="btn-secondary"
        on:click={() => refresh("quest", scopeId)}
        disabled={!scopeId || refreshing === "quest" + scopeId}
      >
        Perbarui quest
      </button>
    </div>
  </div>

  <div class="card mt-6 overflow-x-auto">
    <p class="mono-label mb-2">Snapshot yang ada</p>
    {#if loading}
      <div class="skeleton h-8"></div>
    {:else if snapshots.length === 0}
      <p class="py-2 muted">Belum ada papan peringkat yang dimaterialisasi.</p>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr>
            <th class="py-1">Cakupan</th>
            <th>ID</th>
            <th>Periode</th>
            <th>Diperbarui</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each snapshots as s (s.id)}
            <tr class="border-t">
              <td class="py-1">{s.scope}</td>
              <td class="font-mono text-xs">{s.scope_id?.slice(0, 8) ?? "—"}</td>
              <td>{s.period}</td>
              <td class="text-xs muted">{formatDate(s.updated_at)}</td>
              <td class="text-right">
                <button class="btn-ghost !py-1 text-xs" on:click={() => openEntries(s.id)}
                  >Lihat entri</button
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
        {#if entries.length === 0}
          <p class="mt-2 muted text-sm">Tidak ada entri.</p>
        {:else}
          <ol class="mt-2 space-y-1 text-sm">
            {#each entries as e (e.user_id)}
              <li class="flex items-center justify-between border-b py-1 last:border-0">
                <span>
                  <span class="font-mono text-xs">#{e.rank}</span>
                  {e.display_name ?? e.name ?? e.user_id.slice(0, 8)}
                </span>
                <span class="font-mono text-xs">{e.score_bp} bp</span>
              </li>
            {/each}
          </ol>
        {/if}
      </div>
    {/if}
  </div>
</div>
