<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatNumber, statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

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

  async function load() {
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

  async function reject(id: string) {
    const reason = window.prompt("Alasan penolakan (opsional):") ?? "";
    error = "";
    message = "";
    busy = id;
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

  <div class="mt-4 flex items-center gap-2">
    <label class="mono-label" for="wf">Status</label>
    <select
      id="wf"
      class="input !w-48"
      bind:value={statusFilter}
      on:change={() => {
        page = 1;
        load();
      }}
    >
      <option value="requested">Menunggu review</option>
      <option value="approved">Disetujui</option>
      <option value="rejected">Ditolak</option>
      <option value="submitted">Terkirim</option>
      <option value="confirmed">Selesai</option>
      <option value="">Semua</option>
    </select>
  </div>

  <div class="card mt-4 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(5) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if items.length === 0}
      <p class="py-2 muted">Tidak ada permintaan penarikan.</p>
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
          {#each items as w}
            <tr class="border-t">
              <td class="py-1 font-mono text-xs">{w.user_id.slice(0, 8)}…</td>
              <td class="font-mono text-xs">{w.destination_address.slice(0, 10)}…</td>
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
                    on:click={() => reject(w.id)}
                    disabled={busy === w.id}>{busy === w.id ? "…" : "Tolak"}</button
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
