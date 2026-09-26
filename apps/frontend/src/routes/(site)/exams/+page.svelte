<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Attempt } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import { paginate, formatNumber } from "$lib/utils/format";
  import { reveal } from "$lib/actions/reveal";
  import { formatDate, examCategory, type ExamCategory } from "$lib/utils/format";

  const PAGE_SIZE = 10;

  /** Category tabs: all exams, or one of the two categories (multiple-choice /
   * essay). "mixed" exams (both question kinds) only appear under "Semua". */
  type Filter = "all" | "multiple_choice" | "essay" | "mixed";
  /** Availability derived from is_active + opens_at + closes_at. */
  type Status = "all" | "open" | "upcoming" | "closed";
  type Sort = "recent" | "title" | "duration" | "deadline";

  let exams: Exam[] = [];
  let attempts: Attempt[] = [];
  let loading = true;
  let error = "";
  let currentPage = 1;
  let filter: Filter = "all";
  let status: Status = "all";
  let query = "";
  let sortBy: Sort = "recent";

  $: canManage = hasRole($auth.user, "teacher");

  // --- availability ----------------------------------------------------------
  /** Classify an exam's availability window at view time. */
  function availabilityOf(exam: Exam): Exclude<Status, "all"> {
    const now = Date.now();
    const opens = exam.opens_at ? new Date(exam.opens_at).getTime() : null;
    const closes = exam.closes_at ? new Date(exam.closes_at).getTime() : null;
    if (!exam.is_active) return "closed";
    if (closes !== null && now > closes) return "closed";
    if (opens !== null && now < opens) return "upcoming";
    return "open";
  }

  const statusLabel: Record<Exclude<Status, "all">, string> = {
    open: "Terbuka",
    upcoming: "Akan datang",
    closed: "Ditutup",
  };

  // --- attempts (progress) ---------------------------------------------------
  /** Best completed attempt per exam, so a card can show "Selesai · 85%". */
  $: attemptsByExam = attempts.reduce<Record<string, Attempt[]>>((acc, a) => {
    (acc[a.exam_id] ??= []).push(a);
    return acc;
  }, {});

  function attemptInfo(exam: Exam): {
    count: number;
    best: number | null;
    bestPassed: boolean | null;
    inProgress: boolean;
  } {
    const list = attemptsByExam[exam.id] ?? [];
    const done = list.filter((a) => a.status === "submitted" || a.status === "graded");
    const scored = done.filter((a) => a.score_bp != null);
    const best = scored.length
      ? Math.max(...scored.map((a) => a.score_bp ?? 0))
      : done.length
        ? null
        : null;
    const bestAttempt = scored.find((a) => a.score_bp === best) ?? null;
    return {
      count: list.length,
      best,
      bestPassed: bestAttempt?.passed ?? null,
      inProgress: list.some((a) => a.status === "in_progress"),
    };
  }

  // --- derived buckets -------------------------------------------------------
  $: categorized = exams.map((exam) => ({
    exam,
    category: examCategory(exam),
    status: availabilityOf(exam),
  }));

  $: counts = {
    all: categorized.length,
    multiple_choice: categorized.filter((e) => e.category === "multiple_choice").length,
    essay: categorized.filter((e) => e.category === "essay").length,
    mixed: categorized.filter((e) => e.category === "mixed").length,
  };

  $: statusCounts = {
    open: categorized.filter((e) => e.status === "open").length,
    upcoming: categorized.filter((e) => e.status === "upcoming").length,
    closed: categorized.filter((e) => e.status === "closed").length,
  };

  $: completedCount = exams.filter((e) => {
    const info = attemptInfo(e);
    return info.count > 0 && !info.inProgress;
  }).length;

  $: avgBest = (() => {
    const bests = exams.map((e) => attemptInfo(e).best).filter((b): b is number => b != null);
    if (!bests.length) return null;
    return Math.round(bests.reduce((a, b) => a + b, 0) / bests.length / 100);
  })();

  $: filtered = categorized
    .filter(({ exam, category, status: st }) => {
      if (filter !== "all" && category !== filter) return false;
      if (status !== "all" && st !== status) return false;
      if (query.trim()) {
        const q = query.toLowerCase().trim();
        if (!exam.title.toLowerCase().includes(q)) return false;
      }
      return true;
    })
    .map((e) => e.exam)
    .sort((a, b) => {
      if (sortBy === "title") return a.title.localeCompare(b.title);
      if (sortBy === "duration") return b.duration_minutes - a.duration_minutes;
      if (sortBy === "deadline") {
        const ca = a.closes_at ? new Date(a.closes_at).getTime() : Infinity;
        const cb = b.closes_at ? new Date(b.closes_at).getTime() : Infinity;
        return ca - cb;
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  $: totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedExams = paginate(filtered, currentPage, PAGE_SIZE);

  /** Section headings for the "Semua" view: PG first, then Esai, then campuran. */
  const SECTIONS: { key: ExamCategory; label: string }[] = [
    { key: "multiple_choice", label: "Pilihan Ganda" },
    { key: "essay", label: "Esai" },
    { key: "mixed", label: "Campuran" },
  ];

  // Sections only make sense in the untouched "Semua" view.
  $: groupedView = filter === "all" && status === "all" && !query.trim() && sortBy === "recent";

  function selectFilter(f: Filter) {
    filter = f;
    currentPage = 1;
  }

  function selectStatus(s: Status) {
    status = s;
    currentPage = 1;
  }

  function setQuery() {
    currentPage = 1;
  }

  function resetFilters() {
    filter = "all";
    status = "all";
    query = "";
    sortBy = "recent";
    currentPage = 1;
  }

  function categoryOf(exam: Exam): ExamCategory {
    return examCategory(exam);
  }

  function badgeLabel(category: ExamCategory): string {
    return category === "multiple_choice"
      ? "PG"
      : category === "essay"
        ? "Esai"
        : category === "mixed"
          ? "Campuran"
          : "—";
  }

  async function load() {
    try {
      const [ex, att] = await Promise.all([
        api.get<Exam[]>("/exams?limit=200"),
        api.get<Attempt[]>("/attempts?limit=200").catch(() => [] as Attempt[]),
      ]);
      exams = ex;
      attempts = att;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Ujian — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Asesmen</p>
      <h1 class="mt-1 font-display text-4xl font-bold">Ujian</h1>
      <p class="mt-2 muted">
        Ujian dibagi menjadi <strong>pilihan ganda</strong> (dinilai otomatis) dan
        <strong>esai</strong> (dinilai AI). Pantau status, tenggat, dan skor terbaikmu di sini.
      </p>
    </div>
    {#if canManage}
      <a href="/teacher/exams" class="btn-primary"><Icon name="plus" size="12px" /> Kelola Ujian</a>
    {/if}
  </div>

  {#if error}
    <p class="alert-error mt-4">{error}</p>
  {/if}

  {#if loading}
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {#each Array(4) as _}<div class="skeleton h-24"></div>{/each}
    </div>
    <div class="mt-6 grid gap-5 sm:grid-cols-2">
      {#each Array(2) as _}<div class="skeleton h-32"></div>{/each}
    </div>
  {:else if exams.length === 0}
    <div class="card mt-6 grid place-items-center py-16 text-center">
      <Icon name="file-pen" size="28px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada ujian</p>
      <p class="text-sm muted">Ujian yang dipublikasikan akan muncul di sini.</p>
    </div>
  {:else}
    <!-- Overview metrics -->
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total Ujian</p>
        <p class="mt-1 font-display text-3xl font-bold">{counts.all}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Terbuka</p>
        <p class="mt-1 font-display text-3xl font-bold text-mint" data-role="open-count">
          {statusCounts.open}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Selesai</p>
        <p class="mt-1 font-display text-3xl font-bold">{completedCount}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Rata-rata skor terbaik</p>
        <p class="mt-1 font-display text-3xl font-bold text-highlight">
          {avgBest != null ? `${avgBest}%` : "—"}
        </p>
      </div>
    </div>

    <!-- Category tabs -->
    <div class="mt-6 flex flex-wrap gap-2" role="tablist" aria-label="Kategori ujian">
      <button
        class="btn-ghost !py-1.5"
        class:!border-primary={filter === "all"}
        class:!text-primary={filter === "all"}
        role="tab"
        aria-selected={filter === "all"}
        on:click={() => selectFilter("all")}
      >
        Semua <span class="mono ml-1 text-xs muted">{counts.all}</span>
      </button>
      <button
        class="btn-ghost !py-1.5"
        class:!border-primary={filter === "multiple_choice"}
        class:!text-primary={filter === "multiple_choice"}
        role="tab"
        aria-selected={filter === "multiple_choice"}
        on:click={() => selectFilter("multiple_choice")}
      >
        <Icon name="list-check" size="11px" /> Pilihan Ganda
        <span class="mono ml-1 text-xs muted">{counts.multiple_choice}</span>
      </button>
      <button
        class="btn-ghost !py-1.5"
        class:!border-primary={filter === "essay"}
        class:!text-primary={filter === "essay"}
        role="tab"
        aria-selected={filter === "essay"}
        on:click={() => selectFilter("essay")}
      >
        <Icon name="pen-fancy" size="11px" /> Esai
        <span class="mono ml-1 text-xs muted">{counts.essay}</span>
      </button>
      {#if counts.mixed}
        <button
          class="btn-ghost !py-1.5"
          class:!border-primary={filter === "mixed"}
          class:!text-primary={filter === "mixed"}
          role="tab"
          aria-selected={filter === "mixed"}
          on:click={() => selectFilter("mixed")}
        >
          <Icon name="layer-group" size="11px" /> Campuran
          <span class="mono ml-1 text-xs muted">{counts.mixed}</span>
        </button>
      {/if}
    </div>

    <!-- Search + status + sort -->
    <div class="mt-3 flex flex-wrap items-center gap-2">
      <div class="relative w-full sm:w-64">
        <Icon
          name="magnifying-glass"
          size="12px"
          class="absolute left-3 top-1/2 -translate-y-1/2 muted"
        />
        <input
          class="input text-xs !py-1.5 !pl-9 w-full"
          placeholder="Cari ujian..."
          bind:value={query}
          on:input={setQuery}
          aria-label="Cari ujian"
        />
        {#if query}
          <button
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
            on:click={() => {
              query = "";
              setQuery();
            }}
            aria-label="Bersihkan pencarian"
          >
            ✕
          </button>
        {/if}
      </div>

      <div class="flex items-center gap-1 rounded-sm border p-1 surface text-xs">
        {#each [["all", "Semua"], ["open", "Terbuka"], ["upcoming", "Akan datang"], ["closed", "Ditutup"]] as [val, label]}
          <button
            type="button"
            class="px-2.5 py-1 rounded-xs font-medium transition-colors"
            class:bg-primary={status === val}
            class:text-[#05060A]={status === val}
            class:muted={status !== val}
            on:click={() => selectStatus(val as Status)}
          >
            {label}
          </button>
        {/each}
      </div>

      <select class="input text-xs !py-1.5 w-auto" bind:value={sortBy} aria-label="Urutkan">
        <option value="recent">Terbaru</option>
        <option value="deadline">Tenggat terdekat</option>
        <option value="duration">Durasi terlama</option>
        <option value="title">Judul (A–Z)</option>
      </select>
    </div>

    {#if filtered.length === 0}
      <div class="card mt-6 grid place-items-center py-16 text-center">
        <Icon name="file-pen" size="28px" class="muted" />
        <p class="mt-3 font-semibold">Tidak ada ujian yang cocok</p>
        <p class="text-sm muted">Coba ubah kategori, status, atau pencarianmu.</p>
        <button class="btn-ghost mt-3 !py-1 text-xs" on:click={resetFilters}>Reset Filter</button>
      </div>
    {:else if groupedView}
      {#each SECTIONS as section}
        {@const sectionExams = pagedExams.filter((e) => categoryOf(e) === section.key)}
        {#if sectionExams.length}
          <section class="mt-8">
            <h2 class="hud flex items-center gap-2 font-display text-xl font-bold">
              {section.label}
              <span class="badge badge-indigo">{sectionExams.length}</span>
            </h2>
            <div class="mt-4 grid gap-5 sm:grid-cols-2">
              {#each sectionExams as exam, i}
                {@render examCard(exam, i)}
              {/each}
            </div>
          </section>
        {/if}
      {/each}
    {:else}
      <div class="mt-6 grid gap-5 sm:grid-cols-2">
        {#each pagedExams as exam, i}
          {@render examCard(exam, i)}
        {/each}
      </div>
    {/if}

    <Pagination
      page={currentPage}
      pageSize={PAGE_SIZE}
      total={filtered.length}
      {loading}
      label="ujian"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>

{#snippet examCard(exam: Exam, i: number)}
  {@const st = availabilityOf(exam)}
  {@const info = attemptInfo(exam)}
  {@const category = categoryOf(exam)}
  {@const maxAttempts = exam.max_attempts ?? 1}
  <a
    href={`/exams/${exam.id}`}
    use:reveal={{ delay: i * 40 }}
    class="card lift block"
    data-exam={exam.id}
    data-status={st}
  >
    <div class="flex items-center justify-between">
      <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
        <Icon name="file-pen" size="17px" />
      </span>
      <span class="flex items-center gap-2">
        <span
          class="badge"
          class:badge-indigo={category === "multiple_choice"}
          class:badge-magenta={category === "essay"}
          class:badge-neutral={category === "mixed"}
        >
          {badgeLabel(category)}
        </span>
        <span
          class="badge"
          class:badge-mint={st === "open"}
          class:badge-amber={st === "upcoming"}
          class:badge-neutral={st === "closed"}
        >
          <Icon
            name={st === "open" ? "lock-open" : st === "upcoming" ? "hourglass-half" : "lock"}
            size="9px"
          />
          {statusLabel[st]}
        </span>
      </span>
    </div>

    <h3 class="mt-3 font-display text-lg font-bold">{exam.title}</h3>

    <div class="mono-label mt-2 flex flex-wrap items-center gap-3">
      <span><Icon name="clock" size="10px" /> {exam.duration_minutes} menit</span>
      <span>·</span>
      <span
        ><Icon name="bullseye" size="10px" /> lulus {(exam.passing_score_bp / 100).toFixed(
          0,
        )}%</span
      >
      {#if exam.question_count}
        <span>·</span>
        <span>{exam.question_count} soal</span>
      {/if}
    </div>

    <!-- Deadline -->
    {#if st === "upcoming" && exam.opens_at}
      <p class="mt-2 text-xs muted">
        <Icon name="hourglass-half" size="10px" /> Mulai {formatDate(exam.opens_at)}
      </p>
    {:else if exam.closes_at}
      <p class="mt-2 text-xs muted">
        <Icon name="calendar-xmark" size="10px" /> Ditutup {formatDate(exam.closes_at)}
      </p>
    {/if}

    <!-- Attempt progress -->
    {#if info.inProgress}
      <p class="mt-3 flex items-center gap-2 text-xs text-highlight">
        <Icon name="circle-play" size="11px" /> Sedang dikerjakan
      </p>
    {:else if info.best != null}
      <div class="mt-3 flex items-center justify-between border-t pt-3">
        <span class="flex items-center gap-2 text-xs">
          <Icon
            name={info.bestPassed ? "circle-check" : "circle-xmark"}
            size="12px"
            class={info.bestPassed ? "text-mint" : "text-danger"}
          />
          <span class="font-medium">Skor terbaik {(info.best / 100).toFixed(0)}%</span>
        </span>
        <span class="mono-label text-[10px]">
          {info.count}/{maxAttempts} percobaan
        </span>
      </div>
    {:else if info.count > 0}
      <p class="mt-3 border-t pt-3 text-xs muted">
        <Icon name="hourglass-half" size="10px" /> Menunggu penilaian · {info.count}/{maxAttempts}
        percobaan
      </p>
    {:else}
      <p class="mt-3 flex items-center gap-1 border-t pt-3 text-xs text-primary">
        <Icon name="circle-play" size="11px" /> Kerjakan sekarang
      </p>
    {/if}
  </a>
{/snippet}
