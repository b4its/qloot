<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Task } from "$lib/types";
  import { formatDate, paginate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import CoinIcon from "$lib/components/CoinIcon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import FilterChips from "$lib/components/FilterChips.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";
  import { reveal } from "$lib/actions/reveal";
  import { opt } from "$lib/stores/opt";
  import { onRealtime } from "$lib/stores/realtime";

  interface TaskCompletion {
    id: string;
    task_id: string;
    user_id: string;
    period_key: string;
    reward_key: string;
    completed_at: string;
  }

  const PAGE_SIZE = 10;
  let tasks: Task[] = [];
  let loading = true;
  let error = "";
  let completed: Record<string, boolean> = {};
  let message = "";
  let busy = "";
  let currentPage = 1;

  // Search & Filters
  let searchQuery = "";
  let kindFilter: "all" | "daily" | "weekly" | "learning" | "exam" = "all";
  let statusFilter: "all" | "pending" | "done" = "all";

  const kindLabels: Record<string, string> = {
    daily: "Harian",
    weekly: "Mingguan",
    learning: "Materi",
    exam: "Ujian",
  };

  const kindIcon: Record<string, string> = {
    daily: "calendar-day",
    weekly: "calendar-week",
    learning: "book-open-reader",
    exam: "file-pen",
  };

  $: filteredTasks = tasks.filter((t) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchTitle = t.title.toLowerCase().includes(q);
      const matchDesc = (t.description ?? "").toLowerCase().includes(q);
      if (!matchTitle && !matchDesc) return false;
    }
    if (kindFilter !== "all" && t.kind !== kindFilter) return false;
    if (statusFilter === "done" && !completed[t.id]) return false;
    if (statusFilter === "pending" && completed[t.id]) return false;
    return true;
  });

  $: totalPages = Math.max(1, Math.ceil(filteredTasks.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedTasks = paginate(filteredTasks, currentPage, PAGE_SIZE);

  // Metrics
  $: completedCount = tasks.filter((t) => completed[t.id]).length;
  $: pendingCount = tasks.length - completedCount;
  $: earnedOpt = tasks
    .filter((t) => completed[t.id])
    .reduce((sum, t) => sum + (t.reward_amount || 0), 0);

  $: metrics = [
    { label: "Total Tugas", value: tasks.length },
    { label: "Tugas Selesai", value: completedCount, tone: "text-mint" },
    { label: "Tugas Tersedia", value: pendingCount },
    { label: "OPT Didapat", value: `+${earnedOpt} OPT`, tone: "text-highlight" },
  ];

  $: kindOptions = [
    ["all", `Semua (${tasks.length})`],
    ["daily", "Harian"],
    ["weekly", "Mingguan"],
    ["learning", "Materi"],
    ["exam", "Ujian"],
  ] as const;

  const statusOptions = [
    ["all", "Semua Status"],
    ["pending", "Tersedia"],
    ["done", "Selesai"],
  ] as const;

  function resetFilters() {
    searchQuery = "";
    kindFilter = "all";
    statusFilter = "all";
    currentPage = 1;
  }

  async function load() {
    loading = true;
    error = "";
    try {
      // Completions must NOT be swallowed: silently defaulting to "not completed"
      // would let a student re-run an already-finished daily task.
      const [tasksRes, completionsRes] = await Promise.all([
        api.get<Task[]>("/tasks?limit=200"),
        api.get<TaskCompletion[]>("/tasks/me/completions"),
      ]);
      tasks = tasksRes;
      const compMap: Record<string, boolean> = {};
      for (const c of completionsRes) {
        compMap[c.task_id] = true;
      }
      completed = compMap;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat tugas";
    } finally {
      loading = false;
    }
  }

  async function complete(t: Task) {
    busy = t.id;
    message = "";
    error = "";
    try {
      await api.post(`/tasks/${t.id}/complete`);
      completed = { ...completed, [t.id]: true };
      message = `Tugas "${t.title}" selesai! +${t.reward_amount} OPT ditambahkan ke dompetmu.`;
      // Refresh user's OPT balance header chip
      opt.refresh();
    } catch (e) {
      // Surface failures in the error banner (not the info one) so severity is clear.
      error = e instanceof ApiError ? e.message : "Tidak dapat menyelesaikan tugas";
    } finally {
      busy = "";
    }
  }

  onMount(() => {
    void load();
    return onRealtime(["wallet.updated", "notification:reward", "notification:task"], () => {
      void load();
    });
  });
</script>

<svelte:head><title>Tugas & Misi | QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <p class="mono-label">Misi Harian & Pembelajaran</p>
      <h1 class="mt-1 font-display text-4xl font-bold">Tugas & Misi</h1>
      <p class="mt-2 text-sm muted">
        Selesaikan tugas harian, eksplorasi materi, dan ujian untuk mengumpulkan OryphemToken (OPT).
      </p>
    </div>
  </div>

  {#if message}
    <p class="alert-info mt-4 flex items-center gap-2" role="status" aria-live="polite">
      <Icon name="circle-info" size="14px" class="flex-none text-primary" />
      <span>{message}</span>
    </p>
  {/if}
  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">{error}</p>
  {/if}

  <!-- Overview Metrics -->
  {#if !loading && tasks.length > 0}
    <MetricStrip {metrics} />
  {/if}

  <!-- Search & Filter Controls -->
  <div class="mt-6 flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2 flex-1">
      <div class="w-full sm:w-64">
        <SearchInput
          bind:value={searchQuery}
          placeholder="Cari tugas..."
          label="Cari tugas"
          oninput={() => (currentPage = 1)}
        />
      </div>

      <FilterChips
        options={kindOptions}
        bind:value={kindFilter}
        label="Filter jenis tugas"
        onchange={() => (currentPage = 1)}
      />

      <FilterChips
        options={statusOptions}
        bind:value={statusFilter}
        label="Filter status tugas"
        onchange={() => (currentPage = 1)}
      />
    </div>
  </div>

  <!-- Task Content List -->
  {#if loading}
    <div class="mt-6 space-y-3">
      <Skeleton rows={4} />
    </div>
  {:else if tasks.length === 0}
    <EmptyState
      icon="list-check"
      title="Tidak ada tugas aktif"
      description="Tugas dan misi baru akan muncul di sini secara berkala."
    />
  {:else if filteredTasks.length === 0}
    <EmptyState
      icon="magnifying-glass"
      title="Tidak ada tugas yang cocok"
      description="Tidak ada tugas yang sesuai dengan filter atau pencarian Anda."
      actionLabel="Reset Filter"
      onAction={resetFilters}
    />
  {:else}
    <div class="mt-6 space-y-3">
      {#each pagedTasks as t, i}
        <div
          id={`task-${t.id}`}
          use:reveal={{ delay: i * 30 }}
          class="card flex flex-wrap items-center justify-between gap-4 p-4 hover:border-primary/50 transition-all"
        >
          <div class="flex items-start gap-4">
            <span class="tile h-11 w-11 shrink-0 {completed[t.id] ? 'bg-mint/10' : ''}">
              <Icon
                name={kindIcon[t.kind] ?? "list-check"}
                size="17px"
                class={completed[t.id] ? "text-mint" : "text-primary"}
              />
            </span>
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                <h2 class="font-semibold text-foreground text-sm leading-snug">{t.title}</h2>
                <span class="badge badge-neutral text-[10px]">{kindLabels[t.kind] ?? t.kind}</span>
                {#if t.honor_system}
                  <span
                    class="badge badge-amber text-[10px]"
                    title="Berbasis kejujuran (verifikasi mandiri"
                  >
                    Mandiri
                  </span>
                {/if}
              </div>
              {#if t.description}
                <p class="text-xs muted leading-relaxed">{t.description}</p>
              {/if}
              {#if t.ends_at}
                <p class="text-[11px] muted flex items-center gap-1 pt-0.5">
                  <Icon name="clock" size="10px" />
                  <span>Berakhir {formatDate(t.ends_at)}</span>
                </p>
              {/if}
            </div>
          </div>

          <div class="flex items-center gap-3 shrink-0">
            <span class="mono flex items-center gap-1.5 text-sm font-bold text-highlight">
              <CoinIcon size="15px" />
              <span>+{t.reward_amount} OPT</span>
            </span>
            {#if completed[t.id]}
              <span
                class="badge badge-mint text-xs py-1 px-2.5 flex items-center gap-1.5 font-medium"
              >
                <Icon name="check" size="11px" />
                <span>Selesai</span>
              </span>
            {:else}
              <button
                class="btn-primary !py-1.5 !px-3 text-xs flex items-center gap-1.5"
                on:click={() => complete(t)}
                disabled={busy === t.id}
              >
                {#if busy === t.id}
                  <Icon name="spinner" spin size="11px" />
                  <span>Memproses…</span>
                {:else}
                  <Icon name="check" size="11px" />
                  <span>Selesaikan</span>
                {/if}
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    <Pagination
      page={currentPage}
      pageSize={PAGE_SIZE}
      total={filteredTasks.length}
      {loading}
      label="tugas"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>
