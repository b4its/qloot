<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Task } from "$lib/types";
  import { formatDate, paginate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import { reveal } from "$lib/actions/reveal";
  import { opt } from "$lib/stores/opt";

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
      const [tasksRes, completionsRes] = await Promise.all([
        api.get<Task[]>("/tasks?limit=200"),
        api.get<TaskCompletion[]>("/tasks/me/completions").catch(() => []),
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
    try {
      await api.post(`/tasks/${t.id}/complete`);
      completed = { ...completed, [t.id]: true };
      message = `Tugas "${t.title}" selesai! +${t.reward_amount} OPT ditambahkan ke dompetmu.`;
      // Refresh user's OPT balance header chip
      opt.refresh();
    } catch (e) {
      message = e instanceof ApiError ? e.message : "Tidak dapat menyelesaikan tugas";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Tugas & Misi — QLoot</title></svelte:head>

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
    <p class="alert-info mt-4 flex items-center gap-2">
      <Icon name="circle-info" size="14px" class="flex-none text-primary" />
      <span>{message}</span>
    </p>
  {/if}
  {#if error}
    <p class="alert-error mt-4">{error}</p>
  {/if}

  <!-- Overview Metrics -->
  {#if !loading && tasks.length > 0}
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-3">
        <span class="mono-label text-[10px]">Total Tugas</span>
        <div class="mt-1 font-display text-xl font-bold">{tasks.length}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">Tugas Selesai</span>
        <div class="mt-1 font-display text-xl font-bold text-mint">{completedCount}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">Tugas Tersedia</span>
        <div class="mt-1 font-display text-xl font-bold text-foreground">{pendingCount}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">OPT Didapat</span>
        <div class="mt-1 font-display text-xl font-bold text-highlight">+{earnedOpt} OPT</div>
      </div>
    </div>
  {/if}

  <!-- Search & Filter Controls -->
  <div class="mt-6 flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2 flex-1">
      <div class="relative w-full sm:w-64">
        <input
          type="text"
          class="input text-xs !py-1.5 w-full"
          placeholder="Cari tugas..."
          bind:value={searchQuery}
        />
        {#if searchQuery}
          <button
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
            on:click={() => (searchQuery = "")}
          >
            ✕
          </button>
        {/if}
      </div>

      <!-- Kind filter tabs -->
      <div class="flex items-center gap-1 rounded-sm border p-1 surface text-xs">
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={kindFilter === "all"}
          class:text-[#05060A]={kindFilter === "all"}
          class:muted={kindFilter !== "all"}
          on:click={() => (kindFilter = "all")}
        >
          Semua ({tasks.length})
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={kindFilter === "daily"}
          class:text-[#05060A]={kindFilter === "daily"}
          class:muted={kindFilter !== "daily"}
          on:click={() => (kindFilter = "daily")}
        >
          Harian
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={kindFilter === "weekly"}
          class:text-[#05060A]={kindFilter === "weekly"}
          class:muted={kindFilter !== "weekly"}
          on:click={() => (kindFilter = "weekly")}
        >
          Mingguan
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={kindFilter === "learning"}
          class:text-[#05060A]={kindFilter === "learning"}
          class:muted={kindFilter !== "learning"}
          on:click={() => (kindFilter = "learning")}
        >
          Materi
        </button>
      </div>

      <!-- Status filter tabs -->
      <div class="flex items-center gap-1 rounded-sm border p-1 surface text-xs">
        <button
          type="button"
          class="px-2 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={statusFilter === "all"}
          class:text-[#05060A]={statusFilter === "all"}
          class:muted={statusFilter !== "all"}
          on:click={() => (statusFilter = "all")}
        >
          Semua Status
        </button>
        <button
          type="button"
          class="px-2 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={statusFilter === "pending"}
          class:text-[#05060A]={statusFilter === "pending"}
          class:muted={statusFilter !== "pending"}
          on:click={() => (statusFilter = "pending")}
        >
          Tersedia
        </button>
        <button
          type="button"
          class="px-2 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={statusFilter === "done"}
          class:text-[#05060A]={statusFilter === "done"}
          class:muted={statusFilter !== "done"}
          on:click={() => (statusFilter = "done")}
        >
          Selesai
        </button>
      </div>
    </div>
  </div>

  <!-- Task Content List -->
  {#if loading}
    <div class="mt-6 space-y-3">
      <Skeleton rows={4} />
    </div>
  {:else if tasks.length === 0}
    <div class="card mt-6 grid place-items-center py-16 text-center">
      <Icon name="list-check" size="28px" class="muted" />
      <p class="mt-3 font-semibold text-foreground">Tidak ada tugas aktif</p>
      <p class="text-sm muted">Tugas dan misi baru akan muncul di sini secara berkala.</p>
    </div>
  {:else if filteredTasks.length === 0}
    <div class="card mt-6 text-center py-12 space-y-3">
      <p class="muted text-sm">Tidak ada tugas yang sesuai dengan filter atau pencarian Anda.</p>
      <button class="btn-ghost !py-1 text-xs" on:click={resetFilters}>Reset Filter</button>
    </div>
  {:else}
    <div class="mt-6 space-y-3">
      {#each pagedTasks as t, i}
        <div
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
                    title="Berbasis kejujuran — verifikasi mandiri"
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
            <span class="mono font-bold text-sm text-highlight">+{t.reward_amount} OPT</span>
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
