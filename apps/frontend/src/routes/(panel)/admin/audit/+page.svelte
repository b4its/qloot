<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatDate } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Icon from "$lib/components/Icon.svelte";

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
  let query = "";
  let expanded = new Set<string>();

  async function load() {
    loading = true;
    error = "";
    try {
      const qs = new URLSearchParams({
        limit: String(PAGE),
        offset: String((page - 1) * PAGE),
      });
      if (actionFilter) qs.set("action", actionFilter);
      if (query.trim()) qs.set("q", query.trim());
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

  function toggleExpand(id: string) {
    if (expanded.has(id)) expanded.delete(id);
    else expanded.add(id);
    expanded = new Set(expanded);
  }

  onMount(load);

  // --- metrics over the current page -----------------------------------------
  $: byGroup = logs.reduce<Record<string, number>>((acc, l) => {
    const group = l.action.includes(".") ? l.action.split(".")[0] : l.action;
    acc[group] = (acc[group] ?? 0) + 1;
    return acc;
  }, {});
  $: systemEvents = logs.filter((l) => !l.actor_id).length;

  const ACTION_OPTIONS = [
    "auth.login",
    "auth.login_failed",
    "auth.account_locked",
    "auth.logout_all",
    "auth.password_changed",
    "auth.email_changed",
    "ledger.reconcile",
    "chain.pause",
    "chain.unpause",
  ];
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

  <!-- Search + action filter -->
  <div class="mt-6 flex flex-wrap items-center gap-2">
    <div class="relative flex-1 min-w-[200px]">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        placeholder="Cari tindakan, entitas, aktor, atau request id..."
        bind:value={query}
        on:keydown={(e) => e.key === "Enter" && applyFilter()}
        aria-label="Cari audit"
      />
    </div>
    <select
      class="input text-xs !py-1.5 w-auto"
      bind:value={actionFilter}
      on:change={applyFilter}
      aria-label="Filter tindakan"
    >
      <option value="">Semua tindakan</option>
      {#each ACTION_OPTIONS as a}<option value={a}>{a}</option>{/each}
    </select>
    <button class="btn-primary !py-1.5 text-xs" on:click={applyFilter} disabled={loading}>
      Terapkan
    </button>
    {#if query || actionFilter}
      <button
        class="btn-ghost !py-1.5 text-xs"
        on:click={() => {
          query = "";
          actionFilter = "";
          applyFilter();
        }}>Reset</button
      >
    {/if}
  </div>

  <!-- Metrics over the current page -->
  {#if !loading && logs.length > 0}
    <div class="mt-4 flex flex-wrap items-center gap-2">
      <span class="mono-label text-[10px]">{logs.length} catatan · {systemEvents} sistem</span>
      {#each Object.entries(byGroup) as [group, n]}
        <span class="badge badge-indigo">{group}: {n}</span>
      {/each}
    </div>
  {/if}

  <div class="card mt-4 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(6) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else}
      <table class="w-full text-sm">
        <caption class="sr-only">Log audit</caption>
        <thead class="text-left muted">
          <tr>
            <th class="py-1" scope="col">Waktu</th><th scope="col">Tindakan</th><th scope="col"
              >Entitas</th
            ><th scope="col">Aktor</th><th scope="col">Request</th><th scope="col">Data</th>
          </tr>
        </thead>
        <tbody>
          {#each logs as l (l.id)}
            <tr class="border-t">
              <td class="py-1 text-xs muted">{formatDate(l.created_at)}</td>
              <td><span class="badge badge-neutral">{l.action}</span></td>
              <td class="text-xs">{l.entity_type ?? ""} {l.entity_id?.slice(0, 8) ?? ""}</td>
              <td class="font-mono text-xs">
                {l.actor_id ? `${l.actor_id.slice(0, 8)}…` : "system"}
              </td>
              <td class="font-mono text-xs muted">{l.request_id?.slice(0, 8) ?? "—"}</td>
              <td class="text-xs muted">
                {#if l.data}
                  <button
                    class="text-left hover:text-foreground"
                    on:click={() => toggleExpand(l.id)}
                    aria-label="Lihat data"
                  >
                    {#if expanded.has(l.id)}
                      <span class="mono break-all">{JSON.stringify(l.data)}</span>
                    {:else}
                      <span class="mono">{JSON.stringify(l.data).slice(0, 28)}…</span>
                    {/if}
                  </button>
                {:else}
                  —
                {/if}
              </td>
            </tr>
          {/each}
          {#if logs.length === 0}
            <tr><td colspan="6" class="py-2 muted">Tidak ada catatan yang cocok.</td></tr>
          {/if}
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
