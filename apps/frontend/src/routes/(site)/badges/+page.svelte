<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api/client";
  import type { Badge, UserBadge } from "$lib/types";
  import { relativeTime } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";

  let catalog: Badge[] = [];
  let earned: UserBadge[] = [];
  let loading = true;

  // Map badge codes to Font Awesome icons (backend stores an emoji `icon`).
  const codeIcon: Record<string, string> = {
    first_quest: "bullseye",
    quiz_master: "brain",
    top_3: "medal",
    first_reward: "gem",
    room_regular: "tent",
    perfect_exam: "star",
    learner: "book-open-reader",
  };

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

<svelte:head><title>Badge — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Pencapaian</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Badge</h1>
  <p class="mt-2 muted">Koleksi pencapaian yang kamu buka dengan belajar dan berkompetisi.</p>

  {#if loading}
    <div class="mt-6 grid gap-4 sm:grid-cols-3">
      {#each Array(3) as _}<div class="skeleton h-24"></div>{/each}
    </div>
  {:else}
    <div class="mt-6 grid gap-4 sm:grid-cols-3">
      <div class="card">
        <p class="mono-label">Diperoleh</p>
        <p class="mt-2 font-display text-3xl font-bold text-highlight">{earned.length}</p>
      </div>
      <div class="card">
        <p class="mono-label">Tersedia</p>
        <p class="mt-2 font-display text-3xl font-bold">{catalog.length}</p>
      </div>
      <div class="card">
        <p class="mono-label">Poin badge</p>
        <p class="mt-2 font-display text-3xl font-bold">
          {earned.reduce((s, e) => s + e.badge.points, 0)}
        </p>
      </div>
    </div>

    <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {#each catalog as b}
        {@const owned = earned.find((e) => e.badge.code === b.code)}
        <div class="nft card" class:opacity-50={!earnedCodes.has(b.code)}>
          <div class="flex items-center justify-between">
            <span class="brand-mark grid h-12 w-12 place-items-center rounded-sm">
              <Icon name={codeIcon[b.code] ?? "award"} size="20px" />
            </span>
            {#if owned}
              <span class="badge badge-mint"><Icon name="circle-check" size="10px" /> Diraih</span>
            {:else}
              <span class="badge badge-neutral"><Icon name="lock" size="10px" /> Terkunci</span>
            {/if}
          </div>
          <h2 class="mt-3 font-display text-lg font-bold">{b.name}</h2>
          <p class="text-sm muted">{b.description}</p>
          <div class="mt-3 flex items-center justify-between border-t pt-3 text-xs muted">
            <span class="mono">{b.points} POIN</span>
            {#if owned}<span>· {relativeTime(owned.awarded_at)}</span>{/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
