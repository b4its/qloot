<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Winner } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { bpToPercent, formatDate, statusLabel, paginate } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import Dialog from "$lib/components/Dialog.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import FilterChips from "$lib/components/FilterChips.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";

  const PAGE_SIZE = 12;
  let quests: Quest[] = [];
  let winnersByQuest: Record<string, Winner[]> = {};
  let loading = true;
  let error = "";
  let currentPage = 1;
  let busy = "";

  // Search & filter state
  let searchQuery = "";
  let statusFilter: "all" | "open" | "finalized" | "draft" = "all";

  // Teacher finalization confirmation
  let confirmingFinalizeQuest: Quest | null = null;

  $: canManage = hasRole($auth.user, "teacher");

  interface QuestLeaderboardEntry {
    user_id: string;
    rank: number;
    score_bp: number;
    display_name: string | null;
    reward_amount: number;
    reward_status: string | null;
  }

  interface QuestLeaderboardData {
    scope: string;
    scope_id: string;
    entries: QuestLeaderboardEntry[];
  }

  let viewingQuestLeaderboard: { id: string; title: string } | null = null;
  let questLeaderboardData: QuestLeaderboardData | null = null;
  let questLeaderboardLoading = false;
  let questLeaderboardError = "";

  $: filteredQuests = quests.filter((q) => {
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      const matchTitle = q.title.toLowerCase().includes(query);
      const matchDesc = (q.description ?? "").toLowerCase().includes(query);
      if (!matchTitle && !matchDesc) return false;
    }
    if (statusFilter === "open" && q.status !== "open") return false;
    if (statusFilter === "finalized" && q.status !== "finalized") return false;
    if (statusFilter === "draft" && q.status !== "draft") return false;
    return true;
  });

  $: totalPages = Math.max(1, Math.ceil(filteredQuests.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedQuests = paginate(filteredQuests, currentPage, PAGE_SIZE);

  // Metrics
  $: openQuestsCount = quests.filter((q) => q.status === "open").length;
  $: finalizedQuestsCount = quests.filter((q) => q.status === "finalized").length;
  $: totalRewardsPool = quests.reduce((acc, q) => {
    const rulesTotal = q.rules?.reduce((rAcc, r) => rAcc + (r.reward_amount || 0), 0) ?? 0;
    return acc + rulesTotal;
  }, 0);

  function resetFilters() {
    searchQuery = "";
    statusFilter = "all";
    currentPage = 1;
  }

  $: metrics = [
    { label: "Total Quest", value: quests.length },
    { label: "Quest Aktif", value: openQuestsCount, tone: "text-mint" },
    { label: "Quest Selesai", value: finalizedQuestsCount, tone: "text-indigo-400" },
    { label: "Total Pool Hadiah", value: `${totalRewardsPool} OPT`, tone: "text-highlight" },
  ];

  $: statusOptions = [
    ["all", `Semua (${quests.length})`],
    ["open", "Aktif"],
    ["finalized", "Selesai"],
    ...(canManage ? ([["draft", "Draf"]] as const) : []),
  ] as readonly (readonly [typeof statusFilter, string])[];

  async function openQuestLeaderboard(q: Quest) {
    viewingQuestLeaderboard = { id: q.id, title: q.title };
    questLeaderboardLoading = true;
    questLeaderboardData = null;
    questLeaderboardError = "";
    try {
      questLeaderboardData = await api.get<QuestLeaderboardData>(`/rankings/quests/${q.id}`);
    } catch (e) {
      questLeaderboardError =
        e instanceof ApiError ? e.message : "Gagal memuat papan peringkat quest.";
    } finally {
      questLeaderboardLoading = false;
    }
  }

  function retryQuestLeaderboard() {
    const id = viewingQuestLeaderboard?.id;
    const title = viewingQuestLeaderboard?.title;
    if (id && title) void openQuestLeaderboard({ id, title } as Quest);
  }

  function closeQuestLeaderboard() {
    viewingQuestLeaderboard = null;
    questLeaderboardData = null;
  }

  async function load() {
    loading = true;
    error = "";
    try {
      quests = await api.get<Quest[]>("/quests?limit=200");
      // Fetch winners concurrently and tolerate per-quest failures: a single
      // missing winners list must not blank the whole page.
      const finalized = quests.filter((q) => q.status === "finalized");
      const results = await Promise.allSettled(
        finalized.map((q) => api.get<Winner[]>(`/quests/${q.id}/winners`)),
      );
      results.forEach((res, i) => {
        if (res.status === "fulfilled") winnersByQuest[finalized[i].id] = res.value;
      });
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat quest";
    } finally {
      loading = false;
    }
  }

  async function executeFinalize(q: Quest) {
    if (busy) return;
    error = "";
    busy = `f-${q.id}`;
    confirmingFinalizeQuest = null;
    try {
      await api.post(`/quests/${q.id}/finalize`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal finalisasi quest";
    } finally {
      busy = "";
    }
  }

  async function publish(q: Quest) {
    if (busy) return;
    error = "";
    busy = `p-${q.id}`;
    try {
      await api.post(`/quests/${q.id}/publish`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mempublikasikan quest";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Quest & Hadiah — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <p class="mono-label">Kompetisi & Insentif Gamifikasi</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Quest Tantangan</h1>
      <p class="mt-1 text-sm muted">
        Selesaikan ujian tercepat dengan skor tertinggi untuk memenangkan token OPT.
      </p>
    </div>
    {#if canManage}
      <a href="/teacher/quests" class="btn-primary flex items-center gap-1.5">
        <Icon name="gear" size="12px" />
        <span>Kelola Quest</span>
      </a>
    {/if}
  </div>

  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">
      {error}
    </p>
  {/if}

  <!-- Overview Metrics -->
  {#if !loading && quests.length > 0}
    <MetricStrip {metrics} />
  {/if}

  <!-- Search & Filter Controls -->
  <div class="mt-6 flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2 flex-1">
      <div class="w-full sm:w-64">
        <SearchInput
          bind:value={searchQuery}
          placeholder="Cari judul quest..."
          label="Cari quest"
          oninput={() => (currentPage = 1)}
        />
      </div>

      <!-- Status filter tabs -->
      <FilterChips
        options={statusOptions}
        bind:value={statusFilter}
        label="Filter status quest"
        onchange={() => (currentPage = 1)}
      />
    </div>
  </div>

  <!-- Quest Content Grid -->
  {#if loading}
    <div class="mt-6"><Skeleton rows={4} /></div>
  {:else if quests.length === 0}
    <EmptyState
      icon="trophy"
      title="Belum ada quest yang tersedia"
      description="Nantikan tantangan baru dari guru Anda untuk memenangkan hadiah."
    />
  {:else if filteredQuests.length === 0}
    <EmptyState
      icon="magnifying-glass"
      title="Tidak ada quest yang cocok"
      description="Tidak ada quest yang cocok dengan filter atau pencarian Anda."
      actionLabel="Reset Filter"
      onAction={resetFilters}
    />
  {:else}
    <div class="mt-6 grid gap-6 lg:grid-cols-2">
      {#each pagedQuests as q}
        <div
          class="card lift flex flex-col justify-between hover:border-primary/60 transition-all p-5"
        >
          <div class="space-y-3">
            <div class="flex items-start justify-between gap-3">
              <div>
                <h2 class="font-display text-xl font-bold leading-snug">{q.title}</h2>
                <p class="text-xs muted mt-0.5">
                  Top {q.top_n_winners} Finisher Tercepat & Tertinggi
                </p>
              </div>
              <span
                class="badge text-xs"
                class:badge-mint={q.status === "open"}
                class:badge-indigo={q.status === "finalized"}
                class:badge-neutral={q.status !== "open" && q.status !== "finalized"}
              >
                {statusLabel(q.status)}
              </span>
            </div>

            <p class="text-xs text-foreground/80 leading-relaxed">
              {q.description ?? "Quest cepat untuk peserta teratas."}
            </p>

            <!-- Reward Rules Breakdown -->
            {#if q.rules?.length}
              <div class="rounded-sm border surface p-3 space-y-2">
                <div class="flex items-center justify-between text-xs">
                  <span class="mono-label text-[10px] text-primary">Struktur Hadiah Token</span>
                  <span class="font-mono text-[11px] text-highlight font-bold">
                    Total {q.rules.reduce((acc, r) => acc + (r.reward_amount || 0), 0)} OPT
                  </span>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {#each q.rules as r}
                    <div
                      class="rounded-xs border surface-border bg-surface/50 p-2 text-xs flex items-center justify-between"
                    >
                      <span class="muted text-[11px]">
                        {#if r.rank === 1}🥇 Juara 1{:else if r.rank === 2}🥈 Juara 2{:else if r.rank === 3}🥉
                          Juara 3{:else}#{r.rank}{/if}
                      </span>
                      <span class="font-mono font-bold text-highlight">{r.reward_amount} OPT</span>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            {#if q.closes_at}
              <div class="flex items-center gap-1.5 text-xs muted">
                <Icon name="clock" size="11px" />
                <span>Batas Waktu: {formatDate(q.closes_at)}</span>
              </div>
            {/if}
          </div>

          <!-- Bottom: Winners & Actions -->
          <div class="mt-4 pt-4 border-t space-y-3">
            {#if q.status === "finalized"}
              <div class="space-y-2">
                {#if winnersByQuest[q.id]?.length}
                  <div class="flex items-center justify-between">
                    <h3
                      class="flex items-center gap-1.5 font-display text-xs font-bold text-highlight"
                    >
                      <Icon name="trophy" size="11px" />
                      <span>Pemenang Terkonfirmasi</span>
                    </h3>
                    <span class="text-[10px] muted">{winnersByQuest[q.id].length} siswa juara</span>
                  </div>

                  <div class="space-y-1.5">
                    {#each winnersByQuest[q.id] as w}
                      <div
                        class="flex items-center justify-between text-xs p-1.5 rounded-xs surface border text-foreground"
                      >
                        <span class="font-medium flex items-center gap-1.5">
                          {#if w.rank === 1}
                            <span class="text-amber-400 font-bold">🥇 1</span>
                          {:else if w.rank === 2}
                            <span class="text-slate-300 font-bold">🥈 2</span>
                          {:else if w.rank === 3}
                            <span class="text-amber-600 font-bold">🥉 3</span>
                          {:else}
                            <span class="font-mono font-bold">#{w.rank}</span>
                          {/if}
                          <span class="font-mono text-muted text-[11px]"
                            >{w.user_id.slice(0, 8)}…</span
                          >
                        </span>
                        <div class="flex items-center gap-2 font-mono">
                          <span class="text-primary font-bold">{bpToPercent(w.score_bp)}</span>
                          <span class="text-highlight font-bold">{w.reward_amount} OPT</span>
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}

                <div class="flex justify-end pt-1">
                  <button
                    type="button"
                    class="btn-ghost !py-1 text-xs text-primary flex items-center gap-1.5"
                    on:click={() => openQuestLeaderboard(q)}
                  >
                    <Icon name="ranking-star" size="12px" />
                    <span>Papan Peringkat Quest</span>
                  </button>
                </div>
              </div>
            {/if}

            {#if canManage}
              <div class="flex flex-wrap items-center gap-2 pt-1">
                {#if q.status !== "open"}
                  <button
                    class="btn-secondary !py-1.5 text-xs"
                    on:click={() => publish(q)}
                    disabled={busy === `p-${q.id}`}
                  >
                    {busy === `p-${q.id}` ? "Menerbitkan…" : "Publikasikan"}
                  </button>
                {/if}
                {#if q.status !== "finalized"}
                  <button
                    class="btn-primary !py-1.5 text-xs"
                    on:click={() => (confirmingFinalizeQuest = q)}
                    disabled={busy === `f-${q.id}`}
                  >
                    {busy === `f-${q.id}` ? "Memproses…" : "Finalisasi pemenang"}
                  </button>
                {/if}
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    <Pagination
      page={currentPage}
      pageSize={PAGE_SIZE}
      total={filteredQuests.length}
      {loading}
      label="quest"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>

<!-- Finalization Confirmation Modal (Teacher only) -->
{#if confirmingFinalizeQuest}
  <ConfirmDialog
    title="Konfirmasi Finalisasi Quest"
    description={`Apakah Anda yakin ingin memfinalisasi pemenang untuk quest "${confirmingFinalizeQuest.title}"?`}
    hint="Pemenang ditentukan deterministik dari skor tertinggi dan waktu submit tercepat. Hadiah token OPT dialokasikan ke akun pemenang. Tindakan ini tidak dapat dibatalkan."
    confirmLabel="Ya, Finalisasi Pemenang"
    busy={busy === `f-${confirmingFinalizeQuest.id}`}
    onConfirm={() => executeFinalize(confirmingFinalizeQuest!)}
    close={() => (confirmingFinalizeQuest = null)}
  />
{/if}

<!-- Quest Full Leaderboard Modal -->
{#if viewingQuestLeaderboard}
  <Dialog
    title={viewingQuestLeaderboard.title}
    description="Papan peringkat quest"
    size="max-w-2xl"
    busy={questLeaderboardLoading}
    close={closeQuestLeaderboard}
  >
    <div class="py-2">
      {#if questLeaderboardLoading}
        <Skeleton rows={4} />
      {:else if questLeaderboardError}
        <div class="space-y-2 py-10 text-center text-xs" role="alert">
          <Icon name="triangle-exclamation" size="22px" class="mx-auto text-tertiary" />
          <p class="text-danger">{questLeaderboardError}</p>
          <button class="btn-ghost !py-1 text-xs" on:click={retryQuestLeaderboard}>Coba lagi</button
          >
        </div>
      {:else if questLeaderboardData && questLeaderboardData.entries.length > 0}
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <caption class="sr-only">Papan peringkat quest</caption>
            <thead>
              <tr class="border-b text-muted text-[11px]">
                <th class="py-2.5 px-3" scope="col">#</th>
                <th class="py-2.5 px-3" scope="col">Peserta</th>
                <th class="py-2.5 px-3 text-center" scope="col">Skor</th>
                <th class="py-2.5 px-3 text-right" scope="col">Hadiah</th>
                <th class="py-2.5 px-3 text-center" scope="col">Status Alokasi</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-surface-border">
              {#each questLeaderboardData.entries as e}
                <tr class="hover:bg-surface/50 transition-colors">
                  <td class="py-2.5 px-3 font-mono font-bold">
                    {#if e.rank === 1}
                      <span class="text-amber-400">🥇 1</span>
                    {:else if e.rank === 2}
                      <span class="text-slate-300">🥈 2</span>
                    {:else if e.rank === 3}
                      <span class="text-amber-600">🥉 3</span>
                    {:else}
                      #{e.rank}
                    {/if}
                  </td>
                  <td class="py-2.5 px-3 font-medium text-foreground">
                    {e.display_name ?? `${e.user_id.slice(0, 8)}…`}
                  </td>
                  <td class="py-2.5 px-3 text-center font-mono font-bold text-primary">
                    {bpToPercent(e.score_bp)}
                  </td>
                  <td class="py-2.5 px-3 text-right font-mono font-bold text-highlight">
                    {e.reward_amount} OPT
                  </td>
                  <td class="py-2.5 px-3 text-center">
                    <span
                      class="badge text-[10px]"
                      class:badge-mint={e.reward_status === "confirmed"}
                      class:badge-magenta={e.reward_status === "failed"}
                      class:badge-indigo={e.reward_status !== "confirmed" &&
                        e.reward_status !== "failed"}
                    >
                      {e.reward_status ?? "pending"}
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <div class="py-12 text-center text-xs muted space-y-1">
          <Icon name="trophy" size="24px" class="mx-auto text-muted mb-2" />
          <p>Belum ada data peringkat untuk quest ini.</p>
          <p class="text-[11px]">
            Hasil akan ditampilkan setelah peserta menyelesaikan kuis yang ditargetkan.
          </p>
        </div>
      {/if}
    </div>
    <svelte:fragment slot="footer">
      <div class="flex justify-end">
        <button class="btn-ghost text-xs" on:click={closeQuestLeaderboard}>Tutup</button>
      </div>
    </svelte:fragment>
  </Dialog>
{/if}
