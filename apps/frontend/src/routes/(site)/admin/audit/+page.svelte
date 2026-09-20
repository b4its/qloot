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

  let logs: AuditRow[] = [];
  let error = "";

  onMount(async () => {
    try {
      logs = await api.get<AuditRow[]>("/admin/audit-logs");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load audit logs";
    }
  });
</script>

<svelte:head><title>Audit — QLoot Admin</title></svelte:head>

<h1 class="text-2xl font-bold">Audit log</h1>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-tertiary dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

<div class="card mt-4 overflow-x-auto">
  <table class="w-full text-sm">
    <thead class="text-left muted">
      <tr><th class="py-1">When</th><th>Action</th><th>Entity</th><th>Actor</th><th>Data</th></tr>
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
      {#if logs.length === 0}<tr><td colspan="5" class="py-2 muted">No audit entries.</td></tr>{/if}
    </tbody>
  </table>
</div>
