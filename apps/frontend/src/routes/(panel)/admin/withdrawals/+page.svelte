<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatNumber, statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import Icon from "$lib/components/Icon.svelte";

  interface AdminWithdrawal {
    id: string;
    user_id: string;
    destination_address: string;
    amount: number;
    fee_amount: number;
    status: string;
    reject_reason?: string | null;
    created_at: string;
  }

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  const PAGE = 20;
  let items: AdminWithdrawal[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";
  let page = 1;
  let hasMore = false;
  let statusFilter = "requested";
  let query = "";
  let rejecting: AdminWithdrawal | null = null;
  let rejectReason = "";

  const STATUS_TABS: { value: string; label: string }[] = [
    { value: "requested", label: "Menunggu" },
    { value: "approved", label: "Disetujui" },
    { value: "submitted", label: "Terkirim" },
    { value: "confirmed", label: "Selesai" },
    { value: "rejected", label: "Ditolak" },
    { value: "", label: "Semua" },
  ];

  async function load() {
    if (!hasRole($auth.user, "admin")) return;
    loading = true;
    error = "";
    try {
      const q = statusFilter ? `&status_filter=${statusFilter}` : "";
      items = await api.get<AdminWithdrawal[]>(
        `/admin/withdrawals?limit=${PAGE}&offset=${(page - 1) * PAGE}${q}`,
      );
      hasMore = items.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat penarikan";
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

  async function approve(id: string) {
    error = "";
    message = "";
    busy = id;
    try {
      await api.post(`/admin/withdrawals/${id}/approve`);
      message = "Penarikan disetujui dan diantrekan ke jaringan.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyetujui";
    } finally {
      busy = "";
    }
  }

  async function reject(id: string, reason: string) {
    error = "";
    message = "";
    busy = id;
    rejecting = null;
    rejectReason = "";
    try {
      await api.post(`/admin/withdrawals/${id}/reject`, { reason: reason.trim() || null });
      message = "Penarikan ditolak; dana dikembalikan.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menolak";
    } finally {
      busy = "";
    }
  }

  onMount(load);

  // --- metrics over the current page -----------------------------------------
  $: pageTotal = items.reduce((s, w) => s + w.amount, 0);
  $: pageFees = items.reduce((s, w) => s + (w.fee_amount ?? 0), 0);
  $: requestedCount = items.filter((w) => w.status === "requested").length;

  $: filtered = items.filter((w) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase().trim();
    return w.user_id.toLowerCase().includes(q) || w.destination_address.toLowerCase().includes(q);
  });
</script>

<svelte:head><title>Penarikan — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Penarikan"
    title="Permintaan Penarikan"
    subtitle="Setujui atau tolak permintaan penarikan OPT sebelum dikirim ke jaringan."
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
        class:!text-white={statusFilter === t.value}
        on:click={() => {
          statusFilter = t.value;
          page = 1;
          load();
        }}
      >
        {t.label}
      </button>
    {/each}
  </div>

  <!-- Metrics over the current page -->
  {#if !loading && items.length > 0}
    <div class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Menunggu (halaman ini)</p>
        <p class="mt-1 font-display text-3xl font-bold text-highlight" data-role="requested-count">
          {requestedCount}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total OPT</p>
        <p class="mt-1 font-display text-3xl font-bold">{formatNumber(pageTotal)}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total fee</p>
        <p class="mt-1 font-display text-3xl font-bold text-secondary">{formatNumber(pageFees)}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Baris</p>
        <p class="mt-1 font-display text-3xl font-bold">{items.length}</p>
      </div>
    </div>
  {/if}

  <!-- Search -->
  {#if !loading && items.length > 0}
    <div class="mt-4 relative max-w-md">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        placeholder="Cari ID pengguna atau alamat tujuan..."
        bind:value={query}
        aria-label="Cari penarikan"
      />
    </div>
  {/if}

  <div class="card mt-4 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(5) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if items.length === 0}
      <p class="py-2 muted">Tidak ada permintaan penarikan.</p>
    {:else if filtered.length === 0}
      <p class="py-2 muted">Tidak ada penarikan yang cocok dengan pencarianmu.</p>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">Pengguna</th><th>Tujuan</th><th class="text-right">Jumlah</th><th
              >Status</th
            ><th></th></tr
          >
        </thead>
        <tbody>
          {#each filtered as w (w.id)}
            <tr class="border-t">
              <td class="py-1 font-mono text-xs">{w.user_id.slice(0, 8)}…</td>
              <td class="font-mono text-xs" title={w.destination_address}
                >{w.destination_address.slice(0, 10)}…</td
              >
              <td class="text-right font-mono">
                {formatNumber(w.amount)}{#if w.fee_amount}
                  <span class="text-xs muted">(+{formatNumber(w.fee_amount)} fee)</span>{/if}
              </td>
              <td>
                <span
                  class="badge"
                  class:badge-amber={w.status === "requested"}
                  class:badge-indigo={w.status === "approved" || w.status === "submitted"}
                  class:badge-mint={w.status === "confirmed"}
                  class:badge-magenta={w.status === "rejected" || w.status === "failed"}
                  >{statusLabel(w.status)}</span
                >
              </td>
              <td class="text-right">
                {#if w.status === "requested"}
                  <button class="btn-ghost" on:click={() => approve(w.id)} disabled={busy === w.id}
                    >{busy === w.id ? "…" : "Setujui"}</button
                  >
                  <button
                    class="btn-ghost !text-tertiary"
                    on:click={() => (rejecting = w)}
                    disabled={busy === w.id}>Tolak</button
                  >
                {:else if w.reject_reason}
                  <span class="text-xs muted">{w.reject_reason}</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <Pagination
    {page}
    pageSize={PAGE}
    {hasMore}
    {loading}
    label="penarikan"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>

<!-- Reject confirmation modal -->
{#if rejecting}
  <ConfirmDialog
    title="Tolak Permintaan Penarikan"
    description={`Tolak penarikan ${formatNumber(rejecting.amount)} OPT ke ${rejecting.destination_address.slice(0, 12)}…?`}
    hint="Dana yang diminta akan dikembalikan ke saldo pengguna."
    confirmLabel="Ya, Tolak"
    confirmRole="confirm-reject"
    reason={rejectReason}
    onReason={(v) => (rejectReason = v)}
    reasonPlaceholder="mis. alamat tidak valid"
    busy={busy === rejecting.id}
    onConfirm={() => reject(rejecting!.id, rejectReason)}
    close={() => (rejecting = null)}
  />
{/if}
