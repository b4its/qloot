<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Course, Progress } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import FilterChips from "$lib/components/FilterChips.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";
  import { paginate } from "$lib/utils/format";
  import { reveal } from "$lib/actions/reveal";

  const PAGE_SIZE = 9;
  let courses: Course[] = [];
  let progress: Progress[] = [];
  let loading = true;
  let error = "";
  let currentPage = 1;
  let query = "";
  let statusFilter: "all" | "new" | "started" | "done" = "all";
  let sortBy: "recent" | "progress" | "title" = "recent";
  // Guard so the auth-triggered reload runs at most once per resolved user -
  // otherwise a user with zero courses re-triggers load() forever (load() sets
  // loading=false while courses stays empty).
  let loadedForUser = false;

  $: canManage = hasRole($auth.user, "teacher");
  $: user = $auth.user;

  // Completed lessons per course, for the "continue / done" indicator.
  $: doneByCourse = progress.reduce<Record<string, number>>((acc, p) => {
    if (p.completed) acc[p.course_id] = (acc[p.course_id] ?? 0) + 1;
    return acc;
  }, {});

  function courseStatus(course: Course): "done" | "started" | "new" {
    const done = doneByCourse[course.id] ?? 0;
    if (done <= 0) return "new";
    if (course.lesson_count && done >= course.lesson_count) return "done";
    return "started";
  }

  function coursePct(course: Course): number {
    const total = course.lesson_count ?? 0;
    if (total <= 0) return 0;
    return Math.round(((doneByCourse[course.id] ?? 0) / total) * 100);
  }

  // --- overview metrics ------------------------------------------------------
  // These derive from doneByCourse (i.e. progress); Svelte cannot see through
  // the courseStatus/coursePct function calls, so each statement references
  // `progress` explicitly to establish the reactive dependency.
  $: doneCourses = courses.filter((c) => (void progress, courseStatus(c) === "done")).length;
  $: startedCourses = courses.filter((c) => (void progress, courseStatus(c) === "started")).length;
  $: totalLessons = courses.reduce((s, c) => s + (c.lesson_count ?? 0), 0);
  $: doneLessons = progress.filter((p) => p.completed).length;
  $: overallPct = totalLessons > 0 ? Math.round((doneLessons / totalLessons) * 100) : 0;

  $: metrics = [
    { label: "Pelajaran", value: courses.length },
    { label: "Berjalan", value: startedCourses, tone: "text-highlight" },
    { label: "Selesai", value: doneCourses, tone: "text-mint", role: "done-courses" },
    { label: "Progres", value: `${overallPct}%` },
  ];

  const statusOptions = [
    ["all", "Semua"],
    ["new", "Baru"],
    ["started", "Berjalan"],
    ["done", "Selesai"],
  ] as const;

  // The course most recently progressed but not finished: the natural resume.
  $: resumeCourse =
    (void progress,
    courses
      .filter((c) => courseStatus(c) === "started")
      .sort((a, b) => coursePct(b) - coursePct(a))[0] ?? null);

  // --- filtering + sorting ---------------------------------------------------
  // `progress` referenced so the status/progress filters recompute once loaded.
  $: filtered = courses
    .filter((c) => {
      void progress;
      if (statusFilter !== "all" && courseStatus(c) !== statusFilter) return false;
      if (query.trim() && !c.title.toLowerCase().includes(query.toLowerCase().trim())) return false;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "title") return a.title.localeCompare(b.title);
      if (sortBy === "progress") return coursePct(b) - coursePct(a);
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  $: totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedCourses = paginate(filtered, currentPage, PAGE_SIZE);

  function resetFilters() {
    query = "";
    statusFilter = "all";
    sortBy = "recent";
    currentPage = 1;
  }

  async function load() {
    loading = true;
    error = "";
    try {
      courses = await api.get<Course[]>("/courses?limit=200");
      // Learning progress is only meaningful for signed-in students.
      if (user && !canManage) {
        progress = await api.get<Progress[]>("/me/learning-progress?limit=200");
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
    } finally {
      loading = false;
    }
  }

  onMount(load);
  // Reload once the auth store resolves the current user (at most once).
  $: if (user && !loadedForUser) {
    loadedForUser = true;
    load();
  }
</script>

<svelte:head><title>Pembelajaran | QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Ruang Belajar</p>
      <h1 class="mt-1 font-display text-4xl font-bold">Pelajaran Saya</h1>
      <p class="mt-2 muted">
        Pelajaran untuk kelasmu, lengkap dengan progres dan sertifikat setelah selesai.
      </p>
    </div>
    {#if canManage}
      <a href="/teacher/subjects" class="btn-primary">
        <Icon name="plus" size="12px" /> Buat Pelajaran
      </a>
    {/if}
  </div>

  {#if error}
    <p class="alert-error mt-4">{error}</p>
  {/if}

  {#if loading}
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {#each Array(4) as _}<div class="skeleton h-24"></div>{/each}
    </div>
    <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {#each Array(3) as _}<div class="skeleton h-40"></div>{/each}
    </div>
  {:else if courses.length === 0}
    <EmptyState
      icon="book-open"
      title="Belum ada pelajaran"
      description={canManage
        ? "Buat pelajaran dan targetkan ke sebuah kelas."
        : "Pelajaran untuk kelasmu akan muncul di sini setelah gurumu menerbitkannya."}
      actionHref={canManage ? "/teacher/subjects" : undefined}
      actionLabel={canManage ? "Buat Pelajaran" : undefined}
    />
  {:else}
    <!-- Continue-learning banner -->
    {#if resumeCourse}
      <a
        href={`/learning/${resumeCourse.id}`}
        class="card lift mt-6 flex flex-wrap items-center justify-between gap-4"
        data-role="resume"
      >
        <div class="flex items-center gap-4">
          <span class="tile h-12 w-12">
            <Icon name="circle-play" size="20px" />
          </span>
          <div>
            <p class="mono-label">Lanjutkan belajar</p>
            <p class="font-display text-lg font-bold">{resumeCourse.title}</p>
            <p class="text-xs muted">
              {doneByCourse[resumeCourse.id] ?? 0} / {resumeCourse.lesson_count ?? 0} materi · {coursePct(
                resumeCourse,
              )}% selesai
            </p>
          </div>
        </div>
        <span class="btn-secondary"><Icon name="arrow-right" size="12px" /> Lanjutkan</span>
      </a>
    {/if}

    <!-- Overview metrics -->
    <MetricStrip {metrics} />

    <!-- Search & filters -->
    <div class="mt-5 flex flex-wrap items-center gap-2">
      <SearchInput
        bind:value={query}
        placeholder="Cari pelajaran..."
        label="Cari pelajaran"
        oninput={() => (currentPage = 1)}
      />
      <FilterChips
        options={statusOptions}
        bind:value={statusFilter}
        label="Filter status"
        onchange={() => (currentPage = 1)}
      />
      <select
        class="input text-xs !py-1.5 w-auto"
        bind:value={sortBy}
        on:change={() => (currentPage = 1)}
        aria-label="Urutkan"
      >
        <option value="recent">Terbaru</option>
        <option value="progress">Progres tertinggi</option>
        <option value="title">Judul (A-Z)</option>
      </select>
    </div>

    {#if filtered.length === 0}
      <EmptyState
        icon="magnifying-glass"
        title="Tidak ada pelajaran yang cocok"
        description="Tidak ada pelajaran yang cocok dengan filtermu."
        actionLabel="Reset Filter"
        onAction={resetFilters}
      />
    {:else}
      <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each pagedCourses as course, i (course.id)}
          {@const status = courseStatus(course)}
          {@const done = doneByCourse[course.id] ?? 0}
          {@const total = course.lesson_count ?? 0}
          <div
            use:reveal={{ delay: i * 40 }}
            class="card lift flex flex-col"
            data-course={course.id}
          >
            <div class="flex items-center justify-between">
              <span class="tile h-10 w-10">
                <Icon name="book-open-reader" size="15px" />
              </span>
              {#if status === "done"}
                <span class="badge badge-mint"
                  ><Icon name="circle-check" size="10px" /> Selesai</span
                >
              {:else if status === "started"}
                <span class="badge badge-indigo">Berjalan</span>
              {:else}
                <span class="badge badge-neutral">Baru</span>
              {/if}
            </div>
            <a
              href={`/learning/${course.id}`}
              class="mt-3 font-display text-lg font-bold hover:text-primary"
            >
              {course.title}
            </a>
            <p class="mt-1 line-clamp-2 flex-1 text-sm muted">
              {course.description ?? "Tanpa deskripsi"}
            </p>
            {#if total > 0}
              <div class="mt-3">
                <div
                  class="track h-1.5"
                  role="progressbar"
                  aria-label={`Progres ${course.title}`}
                  aria-valuemin={0}
                  aria-valuemax={total}
                  aria-valuenow={done}
                >
                  <span style={`width:${Math.round((done / total) * 100)}%`}></span>
                </div>
                <p class="mono-label mt-1">{done} / {total} materi selesai</p>
              </div>
            {/if}
            <div class="mt-4 border-t pt-3">
              <a href={`/learning/${course.id}`} class="btn-secondary w-full">
                <Icon name={status === "new" ? "play" : "arrow-right"} size="11px" />
                {status === "new" ? "Mulai" : status === "done" ? "Tinjau" : "Lanjutkan"}
              </a>
            </div>
          </div>
        {/each}
      </div>
      <Pagination
        page={currentPage}
        pageSize={PAGE_SIZE}
        total={filtered.length}
        {loading}
        label="pelajaran"
        onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
        onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
      />
    {/if}
  {/if}
</div>
