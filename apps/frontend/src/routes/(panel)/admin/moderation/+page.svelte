<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatDate } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Pagination from "$lib/components/Pagination.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  interface Report {
    id: string;
    reporter_id: string;
    target_type: string;
    target_id: string;
    reason: string;
    status: string;
    body?: string | null;
    created_at: string;
  }

  const PAGE = 25;
  let reports: Report[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let statusFilter = "open";
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    error = "";
    try {
      const qs = new URLSearchParams({
        limit: String(PAGE),
        offset: String((page - 1) * PAGE),
      });
      if (statusFilter) qs.set("status_filter", statusFilter);
      reports = await api.get<Report[]>(`/community/reports?${qs.toString()}`);
      hasMore = reports.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat antrean moderasi";
    } finally {
      loading = false;
    }
  }

  async function moderate(r: Report, action: "hide" | "delete" | "dismiss") {
    busy = r.id;
    message = "";
    error = "";
    try {
      await api.post(`/community/reports/${r.id}/moderate`, { action });
      message = `Laporan ditindaklanjuti (${action}).`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menindaklanjuti laporan";
    } finally {
      busy = "";
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

<svelte:head><title>Moderasi Komunitas — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Moderasi"
    title="Moderasi Komunitas"
    subtitle="Tinjau laporan pengguna dan sembunyikan, hapus, atau tolak konten."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  <form class="mt-6 flex flex-wrap items-end gap-3" on:submit|preventDefault={applyFilter}>
    <label class="flex flex-col text-xs">
      <span class="muted mb-1">Status</span>
      <select class="input !w-auto" bind:value={statusFilter} on:change={applyFilter}>
        <option value="open">Terbuka</option>
        <option value="actioned">Ditindaklanjuti</option>
        <option value="dismissed">Ditolak</option>
        <option value="">Semua</option>
      </select>
    </label>
    <button class="btn-ghost !py-1.5" type="submit" disabled={loading}>Terapkan</button>
  </form>

  <div class="card mt-6">
    {#if loading}
      <div class="space-y-2">
        {#each Array(4) as _}<div class="skeleton h-12"></div>{/each}
      </div>
    {:else if reports.length === 0}
      <p class="muted">Tidak ada laporan.</p>
    {:else}
      <ul class="divide-y">
        {#each reports as r (r.id)}
          <li class="py-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p class="text-xs mono-label">
                  {r.target_type} · {formatDate(r.created_at)}
                </p>
                <p class="text-sm">
                  <span class="font-medium">Alasan:</span>
                  {r.reason}
                </p>
                {#if r.body}<p class="mt-1 text-sm muted">“{r.body}”</p>{/if}
              </div>
              <span class="badge badge-neutral">{r.status}</span>
            </div>
            {#if r.status === "open"}
              <div class="mt-2 flex flex-wrap gap-2">
                <button
                  class="btn-primary !py-1 text-xs"
                  on:click={() => moderate(r, "hide")}
                  disabled={busy === r.id}>Sembunyikan</button
                >
                <button
                  class="btn-ghost !py-1 text-xs"
                  on:click={() => moderate(r, "delete")}
                  disabled={busy === r.id}>Hapus</button
                >
                <button
                  class="btn-ghost !py-1 text-xs"
                  on:click={() => moderate(r, "dismiss")}
                  disabled={busy === r.id}>Tolak laporan</button
                >
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  <Pagination
    {page}
    pageSize={PAGE}
    {hasMore}
    {loading}
    label="laporan"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>
