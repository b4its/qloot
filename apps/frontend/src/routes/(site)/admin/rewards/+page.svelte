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

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  const PAGE = 20;
  let rewards: Reward[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";
  let page = 1;
  let hasMore = false;

  async function load() {
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

  onMount(load);
</script>

<svelte:head><title>Hadiah — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Hadiah"
    title="Hadiah"
    subtitle="Pantau, ulangi, dan batalkan alokasi OPC."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  <div class="card mt-6 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(5) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if rewards.length === 0}
      <p class="py-2 muted">Belum ada hadiah.</p>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">Kunci</th><th>Pengguna</th><th class="text-right">Jumlah</th><th
              >Status</th
            ><th></th></tr
          >
        </thead>
        <tbody>
          {#each rewards as r}
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
              <td class="text-right">
                {#if r.status === "failed"}<button
                    class="btn-ghost"
                    on:click={() => retry(r.id)}
                    disabled={busy === r.id}>{busy === r.id ? "…" : "Ulangi"}</button
                  >{/if}
                {#if r.status === "pending"}<button
                    class="btn-ghost"
                    on:click={() => cancel(r.id)}
                    disabled={busy === r.id}>{busy === r.id ? "…" : "Batal"}</button
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
