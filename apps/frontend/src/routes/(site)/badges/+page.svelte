<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Badge, UserBadge, BadgeProgress } from "$lib/types";
  import { relativeTime, formatDate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import FilterChips from "$lib/components/FilterChips.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";
  import { reveal } from "$lib/actions/reveal";

  let catalog: Badge[] = [];
  let earned: UserBadge[] = [];
  let progress: BadgeProgress[] = [];
  let loading = true;
  let error = "";

  // Search & filters
  let query = "";
  let rarityFilter: "all" | "legendary" | "epic" | "rare" | "common" = "all";
  let statusFilter: "all" | "unlocked" | "locked" = "all";
  let sortBy: "rarity" | "points" | "progress" | "name" = "rarity";

  // Map badge codes to Font Awesome icons (backend stores an emoji `icon`).
  const codeIcon: Record<string, string> = {
    first_quest: "bullseye",
    quiz_master: "brain",
    top_3: "medal",
    first_reward: "gem",
    room_regular: "tent",
    perfect_exam: "star",
    learner: "book-open-reader",
    xp_500: "star",
    xp_2000: "star",
    xp_5000: "gem",
    xp_10000: "graduation-cap",
    xp_25000: "trophy",
  };

  const rarityOrder: Record<string, number> = { legendary: 0, epic: 1, rare: 2, common: 3 };
  const rarityLabel: Record<string, string> = {
    legendary: "Legendaris",
    epic: "Epik",
    rare: "Langka",
    common: "Umum",
  };
  const rarityClass: Record<string, string> = {
    legendary: "badge-amber",
    epic: "badge-indigo",
    rare: "badge-mint",
    common: "badge-neutral",
  };
  const rarityTint: Record<string, string> = {
    legendary: "border-amber/40",
    epic: "border-indigo/40",
    rare: "border-mint/40",
    common: "",
  };

  async function load() {
    loading = true;
    error = "";
    try {
      // Progress must not be swallowed: a silent empty list renders every
      // locked badge as "0/1", which is a wrong value, not just a missing one.
      const [catalogRes, earnedRes, progressRes] = await Promise.all([
        api.get<Badge[]>("/badges"),
        api.get<UserBadge[]>("/me/badges"),
        api.get<BadgeProgress[]>("/badges/progress"),
      ]);
      catalog = catalogRes;
      earned = earnedRes;
      progress = progressRes;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat badge";
    } finally {
      loading = false;
    }
  }

  onMount(load);

  $: earnedByCode = new Map(earned.map((e) => [e.badge.code, e]));
  $: progressByCode = new Map(progress.map((p) => [p.badge.code, p]));

  /** Progress toward a badge, falling back when the endpoint is unavailable. */
  function progressFor(b: Badge): BadgeProgress {
    return (
      progressByCode.get(b.code) ?? {
        badge: b,
        current: earnedByCode.has(b.code) ? 1 : 0,
        target: 1,
        unlocked: earnedByCode.has(b.code),
      }
    );
  }

  function isUnlocked(b: Badge): boolean {
    return earnedByCode.has(b.code) || progressFor(b).unlocked;
  }

  function pct(p: BadgeProgress): number {
    if (p.target <= 0) return 0;
    return Math.min(100, Math.max(0, Math.round((p.current / p.target) * 100)));
  }

  $: totalPoints = earned.reduce((s, e) => s + e.badge.points, 0);
  $: unlockedCount = catalog.filter((b) => isUnlocked(b)).length;
  $: completionPct = catalog.length ? Math.round((unlockedCount / catalog.length) * 100) : 0;
  $: rarityCounts = catalog.reduce<Record<string, number>>((acc, b) => {
    const r = b.rarity ?? "common";
    acc[r] = (acc[r] ?? 0) + 1;
    return acc;
  }, {});

  $: filtered = catalog
    .filter((b) => {
      if (query.trim()) {
        const q = query.toLowerCase().trim();
        const hit =
          b.name.toLowerCase().includes(q) || (b.description ?? "").toLowerCase().includes(q);
        if (!hit) return false;
      }
      if (rarityFilter !== "all" && (b.rarity ?? "common") !== rarityFilter) return false;
      if (statusFilter === "unlocked" && !isUnlocked(b)) return false;
      if (statusFilter === "locked" && isUnlocked(b)) return false;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "points") return b.points - a.points;
      if (sortBy === "progress") {
        const pa = pct(progressFor(a));
        const pb = pct(progressFor(b));
        return pb - pa;
      }
      return (rarityOrder[a.rarity ?? "common"] ?? 3) - (rarityOrder[b.rarity ?? "common"] ?? 3);
    });

  function resetFilters() {
    query = "";
    rarityFilter = "all";
    statusFilter = "all";
    sortBy = "rarity";
  }

  const statusOptions = [
    ["all", "Semua"],
    ["unlocked", "Diraih"],
    ["locked", "Terkunci"],
  ] as const;

  $: metrics = [
    { label: "Diperoleh", value: unlockedCount, tone: "text-highlight" },
    { label: "Total Badge", value: catalog.length },
    { label: "Kelengkapan", value: `${completionPct}%`, tone: "text-mint" },
    { label: "Poin Badge", value: totalPoints },
  ];
</script>

<svelte:head><title>Badge — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Pencapaian</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Badge</h1>
      <p class="mt-2 max-w-2xl muted">
        Koleksi pencapaian yang kamu buka dengan belajar dan berkompetisi. Badge terkunci
        menampilkan progres menuju syaratnya.
      </p>
    </div>
  </div>

  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">{error}</p>
  {/if}

  {#if loading}
    <div class="mt-6 grid gap-4 sm:grid-cols-4">
      {#each Array(4) as _}<div class="skeleton h-24"></div>{/each}
    </div>
    <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each Array(6) as _}<div class="skeleton h-44"></div>{/each}
    </div>
  {:else if catalog.length === 0}
    <EmptyState
      icon="award"
      title="Belum ada badge"
      description="Katalog badge akan muncul di sini."
    />
  {:else}
    <!-- Overview metrics -->
    <MetricStrip {metrics} />

    <!-- Search & filters -->
    <div class="mt-6 flex flex-wrap items-center gap-2">
      <div class="w-full sm:w-64">
        <SearchInput bind:value={query} placeholder="Cari badge..." label="Cari badge" />
      </div>

      <FilterChips
        options={statusOptions}
        bind:value={statusFilter}
        label="Filter status badge"
        ariaLabel="Filter status badge"
      />

      <select
        class="input text-xs !py-1.5 w-auto"
        bind:value={rarityFilter}
        aria-label="Filter rarity"
      >
        <option value="all">Semua rarity</option>
        <option value="legendary">Legendaris ({rarityCounts["legendary"] ?? 0})</option>
        <option value="epic">Epik ({rarityCounts["epic"] ?? 0})</option>
        <option value="rare">Langka ({rarityCounts["rare"] ?? 0})</option>
        <option value="common">Umum ({rarityCounts["common"] ?? 0})</option>
      </select>

      <select class="input text-xs !py-1.5 w-auto" bind:value={sortBy} aria-label="Urutkan">
        <option value="rarity">Urut: Rarity</option>
        <option value="progress">Urut: Progres</option>
        <option value="points">Urut: Poin</option>
        <option value="name">Urut: Nama</option>
      </select>
    </div>

    {#if filtered.length === 0}
      <EmptyState
        icon="magnifying-glass"
        title="Tidak ada badge yang cocok"
        description="Tidak ada badge yang cocok dengan filter atau pencarianmu."
        actionLabel="Reset Filter"
        onAction={resetFilters}
      />
    {:else}
      <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each filtered as b, i (b.code)}
          {@const owned = earnedByCode.get(b.code)}
          {@const prog = progressFor(b)}
          {@const unlocked = isUnlocked(b)}
          <div
            id={`badge-${b.code}`}
            use:reveal={{ delay: i * 25 }}
            class="nft card border {rarityTint[b.rarity ?? 'common']}"
            class:opacity-70={!unlocked}
            data-badge={b.code}
            data-unlocked={unlocked}
          >
            <div class="flex items-center justify-between">
              <span class="brand-mark grid h-12 w-12 place-items-center rounded-sm">
                <Icon name={codeIcon[b.code] ?? "award"} size="20px" />
              </span>
              {#if unlocked}
                <span class="badge badge-mint" data-role="status">
                  <Icon name="circle-check" size="10px" /> Diraih
                </span>
              {:else}
                <span class="badge badge-neutral" data-role="status">
                  <Icon name="lock" size="10px" /> Terkunci
                </span>
              {/if}
            </div>

            <h2 class="mt-3 font-display text-lg font-bold">{b.name}</h2>
            <p class="text-sm muted">{b.description}</p>

            <!-- Progress toward the criterion (shown for locked badges too) -->
            {#if !unlocked}
              <div class="mt-3">
                <div class="flex items-center justify-between text-xs">
                  <span class="muted">Progres</span>
                  <span class="mono">{prog.current}/{prog.target}</span>
                </div>
                <div
                  class="mt-1.5 h-1.5 w-full overflow-hidden rounded-full"
                  style="background: rgb(var(--line))"
                  role="progressbar"
                  aria-valuenow={prog.current}
                  aria-valuemin={0}
                  aria-valuemax={prog.target}
                  aria-label={`Progres ${b.name}`}
                >
                  <div
                    class="h-full rounded-full bg-primary transition-all"
                    style={`width: ${pct(prog)}%`}
                  ></div>
                </div>
              </div>
            {/if}

            <div class="mt-3 flex items-center justify-between border-t pt-3 text-xs muted">
              <span class="flex items-center gap-2">
                <span class="mono">{b.points} POIN</span>
                <span class="badge {rarityClass[b.rarity ?? 'common']}">
                  {rarityLabel[b.rarity ?? "common"]}
                </span>
              </span>
              {#if owned}<span title={formatDate(owned.awarded_at)}
                  >· {relativeTime(owned.awarded_at)}</span
                >{/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
