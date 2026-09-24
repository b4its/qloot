<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatDate } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  interface AuditRow {
    id: string;
    actor_id?: string | null;
    action: string;
    entity_type?: string | null;
    entity_id?: string | null;
    request_id?: string | null;
    data?: Record<string, unknown> | null;
    created_at: string;
  }

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  const PAGE = 50;
  let logs: AuditRow[] = [];
  let error = "";
  let loading = true;
  let page = 1;
  let hasMore = false;
  // AUTH-05: filter the audit trail by event kind (e.g. auth.login).
  let actionFilter = "";

  async function load() {
    loading = true;
    error = "";
    try {
      const qs = new URLSearchParams({
        limit: String(PAGE),
        offset: String((page - 1) * PAGE),
      });
      if (actionFilter) qs.set("action", actionFilter);
      logs = await api.get<AuditRow[]>(`/admin/audit-logs?${qs.toString()}`);
      hasMore = logs.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat audit log";
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

  function applyFilter() {
    page = 1;
    load();
  }

  onMount(load);
</script>

<svelte:head><title>Log Audit — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Audit"
    title="Log Audit"
    subtitle="Setiap tindakan istimewa tercatat dan dapat ditelusuri."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {error} />

  <form class="mt-6 flex flex-wrap items-end gap-3" on:submit|preventDefault={applyFilter}>
    <label class="flex flex-col text-xs">
      <span class="muted mb-1">Filter tindakan</span>
      <select class="input !w-auto" bind:value={actionFilter} on:change={applyFilter}>
        <option value="">Semua tindakan</option>
        <option value="auth.login">auth.login</option>
        <option value="auth.login_failed">auth.login_failed</option>
        <option value="auth.account_locked">auth.account_locked</option>
        <option value="auth.logout">auth.logout</option>
        <option value="auth.logout_all">auth.logout_all</option>
        <option value="auth.session_revoked">auth.session_revoked</option>
        <option value="auth.password_reset">auth.password_reset</option>
        <option value="auth.password_changed">auth.password_changed</option>
        <option value="auth.email_changed">auth.email_changed</option>
      </select>
    </label>
    <button class="btn-primary !py-1.5" type="submit" disabled={loading}>Terapkan</button>
  </form>

  <div class="card mt-6 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(6) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr>
            <th class="py-1">Waktu</th><th>Tindakan</th><th>Entitas</th><th>Aktor</th><th
              >Request</th
            ><th>Data</th>
          </tr>
        </thead>
        <tbody>
          {#each logs as l}
            <tr class="border-t">
              <td class="py-1 text-xs muted">{formatDate(l.created_at)}</td>
              <td>{l.action}</td>
              <td class="text-xs">{l.entity_type ?? ""} {l.entity_id?.slice(0, 8) ?? ""}</td>
              <td class="font-mono text-xs">{l.actor_id?.slice(0, 8) ?? "system"}…</td>
              <td class="font-mono text-xs muted">{l.request_id?.slice(0, 8) ?? "—"}</td>
              <td class="text-xs muted">{l.data ? JSON.stringify(l.data) : ""}</td>
            </tr>
          {/each}
          {#if logs.length === 0}<tr><td colspan="6" class="py-2 muted">Belum ada catatan.</td></tr
            >{/if}
        </tbody>
      </table>
    {/if}
  </div>

  <Pagination
    {page}
    pageSize={PAGE}
    {hasMore}
    {loading}
    label="catatan"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>
