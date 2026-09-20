<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import { formatNumber } from "$lib/utils/format";

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

  async function load() {
    try {
      rewards = await api.get<RewardRow[]>("/admin/rewards");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load rewards";
    }
  }

  async function retry(id: string) {
    await api.post(`/admin/rewards/${id}/retry`);
    message = "Retry queued";
    await load();
  }
  async function cancel(id: string) {
    await api.post(`/admin/rewards/${id}/cancel`);
    message = "Reward cancelled";
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>Rewards — QLoot Admin</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Admin · Rewards</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Rewards</h1>
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
    <table class="w-full text-sm">
      <thead class="text-left muted">
        <tr
          ><th class="py-1">Key</th><th>User</th><th class="text-right">Amount</th><th>Status</th
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
                class:badge-magenta={r.status === "failed"}>{r.status}</span
              >
            </td>
            <td class="text-right">
              {#if r.status === "failed"}<button class="btn-ghost" on:click={() => retry(r.id)}
                  >Retry</button
                >{/if}
              {#if r.status === "pending"}<button class="btn-ghost" on:click={() => cancel(r.id)}
                  >Cancel</button
                >{/if}
            </td>
          </tr>
        {/each}
        {#if rewards.length === 0}<tr><td colspan="5" class="py-2 muted">No rewards.</td></tr>{/if}
      </tbody>
    </table>
  </div>
</div>
