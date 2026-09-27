<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatNumber } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Icon from "$lib/components/Icon.svelte";

  interface DriftRow {
    account_id: string;
    user_id: string;
    cached: number;
    expected: number;
    user_ref?: string | null;
  }
  interface NegativeRow {
    account_id: string;
    user_id: string;
    cached_balance: number;
    is_in_debt: boolean;
  }

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  let negative: NegativeRow[] = [];
  let drift: DriftRow[] = [];
  let loading = true;
  let reconciling = false;
  let error = "";
  let message = "";
  let query = "";
  // A reconcile run mutates the ledger; require an explicit confirmation.
  let confirmingReconcile = false;

  async function load() {
    loading = true;
    error = "";
    try {
      negative = await api.get<NegativeRow[]>("/admin/ledger/negative");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ledger";
    } finally {
      loading = false;
    }
  }

  async function rerun() {
    confirmingReconcile = false;
    reconciling = true;
    error = "";
    message = "";
    try {
      const res = await api.post<{ drifted: DriftRow[]; count: number }>("/admin/ledger/reconcile");
      drift = res.drifted;
      message =
        res.count === 0
          ? "Rekonsiliasi selesai: tidak ada drift."
          : `Rekonsiliasi memperbaiki ${res.count} akun.`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menjalankan rekonsiliasi";
    } finally {
      reconciling = false;
    }
  }

  onMount(load);

  // --- derived health + metrics ----------------------------------------------
  $: totalDebt = negative.reduce((s, n) => s + Math.abs(n.cached_balance), 0);
  $: frozenCount = negative.filter((n) => n.is_in_debt).length;
  $: healthy = !loading && negative.length === 0;

  $: filteredNegative = negative.filter((n) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase().trim();
    return n.account_id.toLowerCase().includes(q) || n.user_id.toLowerCase().includes(q);
  });
</script>

<svelte:head><title>Ledger — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Ledger"
    title="Rekonsiliasi Ledger"
    subtitle="Cocokkan saldo cache dengan ledger double-entry dan pantau akun berutang."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  <!-- Health banner -->
  {#if !loading}
    <div
      class="card mt-4 flex items-center gap-3 border {healthy
        ? 'border-emerald-500/40'
        : 'border-amber-500/40'}"
      data-role="ledger-health"
    >
      <span class="tile-neutral h-10 w-10">
        <Icon
          name={healthy ? "circle-check" : "triangle-exclamation"}
          size="16px"
          class={healthy ? "text-mint" : "text-highlight"}
        />
      </span>
      <div>
        <p class="font-semibold">
          {healthy ? "Ledger sehat" : `${negative.length} akun berutang`}
        </p>
        <p class="text-xs muted">
          {healthy
            ? "Semua saldo cache cocok dengan ledger double-entry."
            : `${formatNumber(totalDebt)} OPT dalam utang clawback.`}
        </p>
      </div>
      <button
        class="btn-primary ml-auto"
        on:click={() => (confirmingReconcile = true)}
        disabled={reconciling}
      >
        {reconciling ? "Menjalankan…" : "Rekonsiliasi sekarang"}
      </button>
    </div>
  {/if}

  <!-- Metrics -->
  {#if !loading && !healthy}
    <div class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Akun berutang</p>
        <p class="mt-1 font-display text-3xl font-bold" data-role="negative-count">
          {negative.length}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total utang (OPT)</p>
        <p class="mt-1 font-display text-3xl font-bold text-tertiary" data-role="total-debt">
          {formatNumber(totalDebt)}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Ditandai in-debt</p>
        <p class="mt-1 font-display text-3xl font-bold">{frozenCount}</p>
      </div>
    </div>
  {/if}

  {#if !loading && negative.length > 0}
    <div class="mt-4 relative max-w-md">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        placeholder="Cari akun atau pengguna..."
        bind:value={query}
        aria-label="Cari akun"
      />
    </div>
  {/if}

  {#if drift.length}
    <div class="card mt-6">
      <p class="mono-label mb-2">Drift terakhir diperbaiki ({drift.length})</p>
      <table class="w-full text-sm">
        <thead class="text-left muted"
          ><tr
            ><th class="py-1">Akun</th><th>Ref</th><th class="text-right">Cached</th><th
              class="text-right">Seharusnya</th
            ></tr
          ></thead
        >
        <tbody>
          {#each drift as d (d.account_id)}
            <tr class="border-t">
              <td class="py-1 font-mono text-xs">{d.account_id.slice(0, 8)}…</td>
              <td class="font-mono text-xs">{d.user_ref ?? d.user_id.slice(0, 8)}</td>
              <td class="text-right font-mono">{formatNumber(d.cached)}</td>
              <td class="text-right font-mono">{formatNumber(d.expected)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <div class="card mt-6 overflow-x-auto">
    <p class="mono-label mb-2">Akun berutang (saldo negatif)</p>
    {#if loading}
      <div class="skeleton h-8"></div>
    {:else if negative.length === 0}
      <p class="py-2 muted">Tidak ada akun dengan saldo negatif.</p>
    {:else if filteredNegative.length === 0}
      <p class="py-2 muted">Tidak ada akun yang cocok dengan pencarianmu.</p>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted"
          ><tr><th class="py-1">Akun</th><th>Pengguna</th><th class="text-right">Saldo</th></tr
          ></thead
        >
        <tbody>
          {#each filteredNegative as n (n.account_id)}
            <tr class="border-t">
              <td class="py-1 font-mono text-xs">{n.account_id.slice(0, 8)}…</td>
              <td class="font-mono text-xs">{n.user_id.slice(0, 8)}…</td>
              <td class="text-right font-mono text-tertiary">
                {formatNumber(n.cached_balance)}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>

<!-- Reconcile confirmation modal -->
{#if confirmingReconcile}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xs">
    <div class="card w-full max-w-md space-y-4 border-amber-500/40 shadow-2xl">
      <div class="flex items-center gap-2 text-amber-400">
        <Icon name="triangle-exclamation" size="18px" />
        <h3 class="font-display text-lg font-bold">Jalankan Rekonsiliasi Ledger</h3>
      </div>
      <p class="text-xs text-foreground/90 leading-relaxed">
        Rekonsiliasi akan memindai seluruh akun dompet dan menyelaraskan saldo cache dengan ledger
        double-entry. Setiap akun yang drift akan dicatat dan diperbaiki.
      </p>
      <p class="text-xs muted leading-relaxed">Tindakan ini tercatat di audit log.</p>
      <div class="flex items-center justify-end gap-2 border-t pt-3">
        <button class="btn-ghost text-xs" on:click={() => (confirmingReconcile = false)}
          >Batal</button
        >
        <button
          class="btn-primary !bg-amber-500 !text-black text-xs font-semibold"
          on:click={rerun}
          disabled={reconciling}
          data-role="confirm-reconcile"
        >
          {reconciling ? "Menjalankan…" : "Ya, Jalankan"}
        </button>
      </div>
    </div>
  </div>
{/if}
