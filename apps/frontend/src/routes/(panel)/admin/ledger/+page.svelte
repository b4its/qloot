<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { formatNumber } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

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
    reconciling = true;
    error = "";
    message = "";
    try {
      const res = await api.post<{ drifted: DriftRow[]; count: number }>(
        "/admin/ledger/reconcile",
      );
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

  <div class="mt-4">
    <button class="btn-primary" on:click={rerun} disabled={reconciling}>
      {reconciling ? "Menjalankan…" : "Jalankan rekonsiliasi sekarang"}
    </button>
  </div>

  {#if drift.length}
    <div class="card mt-6">
      <p class="mono-label mb-2">Drift terakhir diperbaiki ({drift.length})</p>
      <table class="w-full text-sm">
        <thead class="text-left muted"
          ><tr><th class="py-1">Akun</th><th>Ref</th><th class="text-right">Cached</th><th
              class="text-right">Seharusnya</th
            ></tr></thead
        >
        <tbody>
          {#each drift as d}
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
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted"
          ><tr><th class="py-1">Akun</th><th>Pengguna</th><th class="text-right">Saldo</th></tr
          ></thead
        >
        <tbody>
          {#each negative as n}
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
