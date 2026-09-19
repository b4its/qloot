<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api/client";
  import type { Badge, UserBadge } from "$lib/types";
  import { relativeTime } from "$lib/utils/format";

  let catalog: Badge[] = [];
  let earned: UserBadge[] = [];
  let loading = true;

  onMount(async () => {
    try {
      [catalog, earned] = await Promise.all([
        api.get<Badge[]>("/badges"),
        api.get<UserBadge[]>("/me/badges"),
      ]);
    } finally {
      loading = false;
    }
  });

  $: earnedCodes = new Set(earned.map((e) => e.badge.code));
</script>

<svelte:head><title>Badges — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Badges</h1>
<p class="mt-1 muted">Achievements you unlock by learning, competing and earning OPC.</p>

{#if loading}
  <p class="mt-6 muted">Loading…</p>
{:else}
  <div class="mt-4 grid gap-4 sm:grid-cols-3">
    <div class="card">
      <div class="text-sm muted">Earned</div>
      <div class="text-3xl font-bold text-accent-gold">{earned.length}</div>
    </div>
    <div class="card">
      <div class="text-sm muted">Available</div>
      <div class="text-3xl font-bold">{catalog.length}</div>
    </div>
    <div class="card">
      <div class="text-sm muted">Badge points</div>
      <div class="text-3xl font-bold">
        {earned.reduce((sum, e) => sum + e.badge.points, 0)}
      </div>
    </div>
  </div>

  <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each catalog as b}
      {@const owned = earned.find((e) => e.badge.code === b.code)}
      <div class="card" class:opacity-50={!earnedCodes.has(b.code)}>
        <div class="flex items-center justify-between">
          <span class="text-3xl" aria-hidden="true">{b.icon}</span>
          {#if owned}
            <span class="badge bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-100"
              >✓ Earned</span
            >
          {:else}
            <span class="badge bg-slate-100 text-slate-500 dark:bg-slate-800">Locked</span>
          {/if}
        </div>
        <h2 class="mt-2 font-semibold">{b.name}</h2>
        <p class="text-sm muted">{b.description}</p>
        <div class="mt-2 text-xs muted">
          {b.points} points
          {#if owned}· earned {relativeTime(owned.awarded_at)}{/if}
        </div>
      </div>
    {/each}
  </div>
{/if}
