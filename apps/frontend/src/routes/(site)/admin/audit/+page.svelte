<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import { formatDate } from "$lib/utils/format";

  interface AuditRow {
    id: string;
    actor_id?: string | null;
    action: string;
    entity_type?: string | null;
    entity_id?: string | null;
    data?: Record<string, unknown> | null;
    created_at: string;
  }

  const PAGE = 50;
  let logs: AuditRow[] = [];
  let error = "";
  let loading = true;
  let loadingMore = false;
  let reachedEnd = false;

  async function loadMore() {
    loadingMore = true;
    error = "";
    try {
      const batch = await api.get<AuditRow[]>(
        `/admin/audit-logs?limit=${PAGE}&offset=${logs.length}`,
      );
      logs = [...logs, ...batch];
      if (batch.length < PAGE) reachedEnd = true;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat audit log";
    } finally {
      loading = false;
      loadingMore = false;
    }
  }

  onMount(loadMore);
</script>

<svelte:head><title>Audit — QLoot Admin</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Admin · Audit</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Audit log</h1>
  <p class="mt-2 muted">Setiap tindakan istimewa tercatat dan dapat ditelusuri.</p>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  <div class="card mt-6 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(6) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr>
            <th class="py-1">When</th><th>Action</th><th>Entity</th><th>Actor</th><th>Data</th>
          </tr>
        </thead>
        <tbody>
          {#each logs as l}
            <tr class="border-t">
              <td class="py-1 text-xs muted">{formatDate(l.created_at)}</td>
              <td>{l.action}</td>
              <td class="text-xs">{l.entity_type ?? ""} {l.entity_id?.slice(0, 8) ?? ""}</td>
              <td class="font-mono text-xs">{l.actor_id?.slice(0, 8) ?? "system"}…</td>
              <td class="text-xs muted">{l.data ? JSON.stringify(l.data) : ""}</td>
            </tr>
          {/each}
          {#if logs.length === 0}<tr><td colspan="5" class="py-2 muted">Belum ada catatan.</td></tr
            >{/if}
        </tbody>
      </table>
    {/if}
  </div>

  {#if !loading && !reachedEnd}
    <div class="mt-4 flex justify-center">
      <button class="btn-secondary" on:click={loadMore} disabled={loadingMore}>
        {loadingMore ? "Memuat…" : "Muat lebih banyak"}
      </button>
    </div>
  {/if}
</div>
