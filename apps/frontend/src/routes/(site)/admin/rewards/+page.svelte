<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import { formatNumber, statusLabel } from "$lib/utils/format";

  interface RewardRow {
    id: string;
    reward_key: string;
    user_id: string;
    amount: number;
    status: string;
    quest_id?: string | null;
    created_at: string;
  }

  let rewards: RewardRow[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";

  async function load() {
    loading = true;
    error = "";
    try {
      rewards = await api.get<RewardRow[]>("/admin/rewards?limit=100");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat hadiah";
    } finally {
      loading = false;
    }
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
  <p class="mono-label">Admin · Hadiah</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Hadiah</h1>
  <p class="mt-2 muted">Pantau, ulangi, dan batalkan alokasi OPC.</p>

  {#if message}<p class="alert-ok mt-4">
      {message}
    </p>{/if}
  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

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
              <td class="font-mono text-xs">{r.user_id.slice(0, 8)}…</td>
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
</div>
