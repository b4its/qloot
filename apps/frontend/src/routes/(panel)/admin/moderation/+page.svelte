<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatDate } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

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
  let query = "";
  // Destructive actions require an explicit confirmation.
  let confirming: { report: Report; action: "hide" | "delete" } | null = null;

  const STATUS_TABS: { value: string; label: string }[] = [
    { value: "open", label: "Terbuka" },
    { value: "actioned", label: "Ditindaklanjuti" },
    { value: "dismissed", label: "Ditolak" },
    { value: "", label: "Semua" },
  ];

  async function load() {
    if (!hasRole($auth.user, "admin")) return;
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
    confirming = null;
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

  // --- metrics + search (over the current page) ------------------------------
  $: openCount = reports.filter((r) => r.status === "open").length;
  $: actionedCount = reports.filter((r) => r.status === "actioned").length;
  $: dismissedCount = reports.filter((r) => r.status === "dismissed").length;
  $: byType = reports.reduce<Record<string, number>>((acc, r) => {
    acc[r.target_type] = (acc[r.target_type] ?? 0) + 1;
    return acc;
  }, {});

  $: filtered = reports.filter((r) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase().trim();
    return r.reason.toLowerCase().includes(q) || (r.body ?? "").toLowerCase().includes(q);
  });
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

  <!-- Status tabs -->
  <div
    class="mt-4 flex flex-wrap gap-1 rounded-sm border p-1 w-fit"
    role="tablist"
    aria-label="Status"
  >
    {#each STATUS_TABS as t (t.value)}
      <button
        role="tab"
        aria-selected={statusFilter === t.value}
        class="btn-ghost !px-3 !py-1.5 text-xs"
        class:bg-primary={statusFilter === t.value}
        class:!text-[#05060A]={statusFilter === t.value}
        on:click={() => {
          statusFilter = t.value;
          applyFilter();
        }}
      >
        {t.label}
      </button>
    {/each}
  </div>

  <!-- Metrics over the current page -->
  {#if !loading && reports.length > 0}
    <div class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Terbuka</p>
        <p class="mt-1 font-display text-3xl font-bold text-highlight" data-role="open-count">
          {openCount}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Ditindaklanjuti</p>
        <p class="mt-1 font-display text-3xl font-bold text-mint">{actionedCount}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Ditolak</p>
        <p class="mt-1 font-display text-3xl font-bold">{dismissedCount}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Jenis konten</p>
        <p class="mt-1 text-xs muted">
          {#each Object.entries(byType) as [type, n]}
            <span class="badge badge-indigo mr-1">{type}: {n}</span>
          {/each}
        </p>
      </div>
    </div>

    <!-- Search -->
    <div class="mt-4 relative max-w-md">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        placeholder="Cari alasan atau isi konten..."
        bind:value={query}
        aria-label="Cari laporan"
      />
    </div>
  {/if}

  <div class="card mt-6">
    {#if loading}
      <div class="space-y-2">
        {#each Array(4) as _}<div class="skeleton h-12"></div>{/each}
      </div>
    {:else if reports.length === 0}
      <p class="muted">Tidak ada laporan.</p>
    {:else if filtered.length === 0}
      <p class="muted">Tidak ada laporan yang cocok dengan pencarianmu.</p>
    {:else}
      <ul class="divide-y">
        {#each filtered as r (r.id)}
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
              <span
                class="badge"
                class:badge-mint={r.status === "actioned"}
                class:badge-neutral={r.status === "dismissed"}
                class:badge-amber={r.status === "open"}>{r.status}</span
              >
            </div>
            {#if r.status === "open"}
              <div class="mt-2 flex flex-wrap gap-2">
                <button
                  class="btn-primary !py-1 text-xs"
                  on:click={() => (confirming = { report: r, action: "hide" })}
                  disabled={busy === r.id}>Sembunyikan</button
                >
                <button
                  class="btn-ghost !py-1 text-xs !text-tertiary"
                  on:click={() => (confirming = { report: r, action: "delete" })}
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

<!-- Moderation confirmation modal -->
{#if confirming}
  <ConfirmDialog
    title={confirming.action === "delete" ? "Hapus Konten" : "Sembunyikan Konten"}
    description={confirming.action === "delete"
      ? "Konten yang dilaporkan akan dihapus permanen."
      : "Konten yang dilaporkan akan disembunyikan dari feed publik."}
    hint={`Alasan laporan: “${confirming.report.reason}”`}
    confirmLabel={`Ya, ${confirming.action === "delete" ? "Hapus" : "Sembunyikan"}`}
    confirmRole="confirm-moderate"
    busy={busy === confirming.report.id}
    onConfirm={() => moderate(confirming!.report, confirming!.action)}
    close={() => (confirming = null)}
  />
{/if}
