<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatNumber, statusLabel } from "$lib/utils/format";
  import type { Reward } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import Icon from "$lib/components/Icon.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  const PAGE = 20;
  let rewards: Reward[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";
  let page = 1;
  let hasMore = false;
  let query = "";
  let statusFilter: "all" | "confirmed" | "pending" | "failed" = "all";
  let confirmingCancel: Reward | null = null;

  async function load() {
    if (!hasRole($auth.user, "admin")) return;
    loading = true;
    error = "";
    try {
      rewards = await api.get<Reward[]>(`/admin/rewards?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = rewards.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat hadiah";
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

  // --- metrics + filtering (over the current page) ---------------------------
  $: confirmedCount = rewards.filter((r) => r.status === "confirmed").length;
  $: pendingCount = rewards.filter((r) => r.status === "pending").length;
  $: failedCount = rewards.filter((r) => r.status === "failed").length;
  $: failedTotal = rewards.filter((r) => r.status === "failed").reduce((s, r) => s + r.amount, 0);

  $: filtered = rewards.filter((r) => {
    if (statusFilter !== "all" && r.status !== statusFilter) return false;
    if (query.trim()) {
      const q = query.toLowerCase().trim();
      if (
        !r.reward_key.toLowerCase().includes(q) &&
        !(r.user_id ?? "").toLowerCase().includes(q) &&
        !(r.reward_type ?? "").toLowerCase().includes(q)
      )
        return false;
    }
    return true;
  });

  async function retry(id: string) {
    error = "";
    message = "";
    busy = id;
    try {
      await api.post(`/admin/rewards/${id}/retry`);
      message = "Percobaan ulang diantrekan.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengulangi";
    } finally {
      busy = "";
    }
  }

  async function cancel(id: string) {
    error = "";
    message = "";
    busy = id;
    confirmingCancel = null;
    try {
      await api.post(`/admin/rewards/${id}/cancel`);
      message = "Hadiah dibatalkan.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membatalkan";
    } finally {
      busy = "";
    }
  }

  // --- manual adjustment (audited, idempotent) ---
  let adjUserId = "";
  let adjAmount = 0;
  let adjReason = "";
  let adjBusy = false;

  async function adjust() {
    error = "";
    message = "";
    // Mirror the backend constraints (reason >= 3 chars, amount within +-1e6)
    // so the user gets an inline message instead of a raw 422.
    if (!adjUserId.trim() || adjAmount === 0) {
      error = "Isi ID pengguna dan jumlah penyesuaian.";
      return;
    }
    if (adjReason.trim().length < 3) {
      error = "Alasan minimal 3 karakter.";
      return;
    }
    if (Math.abs(adjAmount) > 1_000_000) {
      error = "Jumlah penyesuaian maksimal 1.000.000 OPT.";
      return;
    }
    adjBusy = true;
    try {
      await api.post("/admin/rewards/adjust", {
        user_id: adjUserId.trim(),
        amount: Number(adjAmount),
        reason: adjReason.trim(),
        idempotency_key: `adj-${adjUserId.trim()}-${Date.now()}`,
      });
      message = "Penyesuaian saldo diterapkan.";
      adjUserId = "";
      adjAmount = 0;
      adjReason = "";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyesuaikan";
    } finally {
      adjBusy = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Hadiah | QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Hadiah"
    title="Hadiah"
    subtitle="Pantau, ulangi, dan batalkan alokasi OPT."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  <div class="card mt-6">
    <p class="mono-label">Penyesuaian saldo manual</p>
    <p class="mt-1 text-xs muted">
      Tercatat di audit log. Jumlah positif menambah, negatif mengurangi.
    </p>
    <div class="mt-3 grid gap-3 sm:grid-cols-4">
      <input
        class="input"
        placeholder="ID pengguna"
        aria-label="ID pengguna untuk penyesuaian"
        bind:value={adjUserId}
      />
      <input
        class="input"
        type="number"
        placeholder="Jumlah OPT"
        aria-label="Jumlah OPT (positif menambah, negatif mengurangi)"
        bind:value={adjAmount}
      />
      <input
        class="input"
        placeholder="Alasan (wajib)"
        aria-label="Alasan penyesuaian (wajib)"
        bind:value={adjReason}
      />
      <button
        class="btn-secondary"
        on:click={adjust}
        disabled={adjBusy || !adjUserId.trim() || adjReason.trim().length < 3 || adjAmount === 0}
        >{adjBusy ? "Menyimpan…" : "Terapkan"}</button
      >
    </div>
  </div>

  <!-- Metrics -->
  {#if !loading && rewards.length > 0}
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Terkonfirmasi</p>
        <p class="mt-1 font-display text-3xl font-bold text-mint" data-role="confirmed-count">
          {confirmedCount}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Tertunda</p>
        <p class="mt-1 font-display text-3xl font-bold text-highlight">{pendingCount}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Gagal</p>
        <p class="mt-1 font-display text-3xl font-bold" class:text-danger={failedCount > 0}>
          {failedCount}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">OPT tertahan (gagal)</p>
        <p class="mt-1 font-display text-3xl font-bold">{formatNumber(failedTotal)}</p>
      </div>
    </div>
  {/if}

  <!-- Search + status filter -->
  {#if !loading && rewards.length > 0}
    <div class="mt-4 flex flex-wrap items-center gap-2">
      <div class="relative flex-1 min-w-[200px]">
        <Icon
          name="magnifying-glass"
          size="12px"
          class="absolute left-3 top-1/2 -translate-y-1/2 muted"
        />
        <input
          class="input text-xs !py-1.5 !pl-8 w-full"
          placeholder="Cari kunci, pengguna, atau jenis..."
          bind:value={query}
          aria-label="Cari hadiah"
        />
      </div>
      <div class="flex items-center gap-1 rounded-sm border p-1 surface text-xs">
        {#each [["all", "Semua"], ["confirmed", "Terkonfirmasi"], ["pending", "Tertunda"], ["failed", "Gagal"]] as [val, label]}
          <button
            type="button"
            class="px-2.5 py-1 rounded-xs font-medium transition-colors"
            class:bg-primary={statusFilter === val}
            class:text-[#05060A]={statusFilter === val}
            class:muted={statusFilter !== val}
            on:click={() => (statusFilter = val as typeof statusFilter)}
          >
            {label}
          </button>
        {/each}
      </div>
    </div>
  {/if}

  <div class="card mt-4 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(5) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if rewards.length === 0}
      <p class="py-2 muted">Belum ada hadiah.</p>
    {:else if filtered.length === 0}
      <p class="py-2 muted">Tidak ada hadiah yang cocok dengan filtermu.</p>
    {:else}
      <table class="w-full text-sm">
        <caption class="sr-only">Daftar hadiah</caption>
        <thead class="text-left muted">
          <tr
            ><th class="py-1" scope="col">Kunci</th><th scope="col">Pengguna</th><th
              class="text-right"
              scope="col">Jumlah</th
            ><th scope="col">Status</th><th scope="col">Catatan</th><th scope="col"></th></tr
          >
        </thead>
        <tbody>
          {#each filtered as r (r.id)}
            <tr class="border-t">
              <td class="py-1 font-mono text-xs">{r.reward_key.slice(0, 10)}…</td>
              <td class="font-mono text-xs">{(r.user_id ?? "").slice(0, 8)}…</td>
              <td class="text-right font-mono">{formatNumber(r.amount)}</td>
              <td>
                <span
                  class="badge"
                  class:badge-mint={r.status === "confirmed"}
                  class:badge-amber={r.status === "pending"}
                  class:badge-magenta={r.status === "failed"}>{statusLabel(r.status)}</span
                >
              </td>
              <td class="max-w-[240px] truncate text-xs muted" title={r.error_message ?? ""}>
                {r.error_message ?? "-"}
              </td>
              <td class="text-right">
                {#if r.status === "failed"}<button
                    class="btn-ghost"
                    on:click={() => retry(r.id)}
                    disabled={busy === r.id}>{busy === r.id ? "…" : "Ulangi"}</button
                  >{/if}
                {#if r.status === "pending"}<button
                    class="btn-ghost"
                    on:click={() => (confirmingCancel = r)}
                    disabled={busy === r.id}>Batal</button
                  >{/if}
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
    label="hadiah"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>

<!-- Cancel confirmation modal -->
{#if confirmingCancel}
  <ConfirmDialog
    title="Konfirmasi Batalkan Hadiah"
    description={`Batalkan hadiah ${confirmingCancel.reward_key.slice(0, 12)}… senilai ${formatNumber(confirmingCancel.amount)} OPT?`}
    hint="Hadiah yang tertunda akan dibatalkan dan tidak dikirim ke chain. Tindakan ini tercatat di audit log."
    confirmLabel="Ya, Batalkan"
    confirmRole="confirm-cancel-reward"
    busy={busy === confirmingCancel.id}
    onConfirm={() => cancel(confirmingCancel!.id)}
    close={() => (confirmingCancel = null)}
  />
{/if}
