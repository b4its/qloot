<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Course, Progress } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";
  import { paginate } from "$lib/utils/format";
  import { reveal } from "$lib/actions/reveal";

  const PAGE_SIZE = 12;
  type Sort = "recent" | "title" | "progress" | "lessons";

  let subjects: Course[] = [];
  let progress: Progress[] = [];
  let loading = true;
  let error = "";
  // Progress is a secondary fetch; if it fails we keep the catalog usable but
  // warn instead of silently painting every course as un-started (0%).
  let progressError = "";
  let query = "";
  let classFilter = "all";
  let subjectFilter = "all";
  let sortBy: Sort = "recent";
  let currentPage = 1;
  let mounted = false;
  let loadStarted = false;
  // Track the last-seen ?q= param so we only overwrite the box when the URL
  // itself changes (header search / /paths deep links), not while typing.
  let lastQ = "";

  $: qParam = $page.url.searchParams.get("q") ?? "";
  $: if (qParam !== lastQ) {
    lastQ = qParam;
    // Mirror the URL both ways: clearing ?q= must also clear the search box.
    query = qParam;
  }

  $: user = $auth.user;
  $: canManage = hasRole(user, "teacher");
  $: classes = [...new Set(subjects.map((s) => s.class_code).filter(Boolean))] as string[];
  $: subjectOptions = [...new Set(subjects.map((s) => s.subject).filter(Boolean))] as string[];

  // --- per-course learning progress ------------------------------------------
  /** Completed lesson count per course from the student's progress rows. */
  $: completedByCourse = progress.reduce<Record<string, number>>((acc, p) => {
    if (p.completed) acc[p.course_id] = (acc[p.course_id] ?? 0) + 1;
    return acc;
  }, {});

  function courseProgress(c: Course): { done: number; total: number; pct: number } {
    const total = c.lesson_count ?? 0;
    const done = Math.min(completedByCourse[c.id] ?? 0, total);
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    return { done, total, pct };
  }

  $: filtered = subjects
    .filter((s) => {
      const q = query.toLowerCase();
      const matchesQuery =
        !q ||
        s.title.toLowerCase().includes(q) ||
        (s.subject ?? "").toLowerCase().includes(q) ||
        (s.owner_name ?? "").toLowerCase().includes(q);
      const matchesClass = classFilter === "all" || s.class_code === classFilter;
      const matchesSubject = subjectFilter === "all" || s.subject === subjectFilter;
      return matchesQuery && matchesClass && matchesSubject;
    })
    .sort((a, b) => {
      if (sortBy === "title") return a.title.localeCompare(b.title);
      if (sortBy === "lessons") return (b.lesson_count ?? 0) - (a.lesson_count ?? 0);
      if (sortBy === "progress") return courseProgress(b).pct - courseProgress(a).pct;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  // Reset to the first page whenever the filter set changes.
  $: totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: paged = paginate(filtered, currentPage, PAGE_SIZE);

  // --- overview metrics ------------------------------------------------------
  $: totalLessons = subjects.reduce((sum, s) => sum + (s.lesson_count ?? 0), 0);
  $: completedLessons = progress.filter((p) => p.completed).length;
  $: overallPct = totalLessons > 0 ? Math.round((completedLessons / totalLessons) * 100) : 0;
  $: finishedCourses = subjects.filter((c) => {
    const { done, total } = courseProgress(c);
    return total > 0 && done >= total;
  }).length;

  function resetFilters() {
    query = "";
    classFilter = "all";
    subjectFilter = "all";
    sortBy = "recent";
    currentPage = 1;
  }

  async function load() {
    loading = true;
    error = "";
    progressError = "";
    try {
      subjects = await api.get<Course[]>("/courses?limit=200");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
      loading = false;
      return;
    }
    // Progress feeds the per-course bars; a failure here must not blank the
    // catalog, but it should say so rather than show a misleading 0%.
    try {
      progress = await api.get<Progress[]>("/me/learning-progress?limit=200");
    } catch (e) {
      progress = [];
      progressError =
        e instanceof ApiError
          ? `Progres belajar belum dapat dimuat: ${e.message}`
          : "Progres belajar belum dapat dimuat.";
    }
    loading = false;
  }

  onMount(() => {
    mounted = true;
  });

  // Wait for the root auth bootstrap before touching protected course APIs.
  // Anonymous visitors receive a deliberate product preview instead of a 401.
  $: if (mounted && !$auth.loading && !loadStarted) {
    loadStarted = true;
    if (user) void load();
    else loading = false;
  }
</script>

<svelte:head><title>Pelajaran | QLoot</title></svelte:head>

<div class="dotgrid relative">
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-12 sm:px-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p class="mono-label">Pelajaran</p>
        <h1 class="mt-2 font-display text-4xl font-bold">Daftar pelajaran</h1>
        <p class="mt-2 max-w-2xl muted">
          {#if user}
            Pelajaran yang dapat kamu akses{#if user.class_code}
              : kelas
              <span class="font-semibold text-ink"
                >{user.class_code}{user.class_type ? ` · ${user.class_type}` : ""}</span
              >{/if}.
          {:else}
            Masuk untuk melihat pelajaran sesuai kelasmu.
          {/if}
        </p>
      </div>
      {#if canManage}
        <a href="/teacher" class="btn-primary"><Icon name="plus" size="12px" /> Kelola Pelajaran</a>
      {/if}
    </div>

    {#if !loading && !user}
      <section class="mt-8 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]" aria-labelledby="catalog-preview">
        <div class="card !p-7 sm:!p-9">
          <span class="neon-chip"><Icon name="sparkles" size="10px" /> Ruang belajar personal</span>
          <h2 id="catalog-preview" class="mt-4 text-2xl font-bold sm:text-3xl">
            Pelajaran disesuaikan dengan kelasmu
          </h2>
          <p class="mt-3 max-w-2xl text-ink2">
            Masuk untuk melihat materi dari guru, progres tiap pelajaran, ujian, dan rekomendasi
            aktivitas yang sesuai dengan kelasmu.
          </p>
          <div class="mt-6 flex flex-wrap gap-3">
            <a href="/login?next=%2Fcourses" class="btn-primary">
              <Icon name="right-to-bracket" size="12px" /> Masuk untuk melihat katalog
            </a>
            <a href="/register" class="btn-secondary">Buat akun siswa</a>
          </div>
        </div>
        <div class="card !p-7">
          <p class="mono-label">Yang akan kamu dapatkan</p>
          <ul class="mt-4 space-y-4 text-sm">
            <li class="flex gap-3">
              <Icon name="route" class="mt-0.5 text-secondary" /> Jalur belajar dan progres yang terukur
            </li>
            <li class="flex gap-3">
              <Icon name="robot" class="mt-0.5 text-secondary" /> Bantuan AI berbasis materi guru
            </li>
            <li class="flex gap-3">
              <Icon name="certificate" class="mt-0.5 text-secondary" /> Ujian, reward, dan sertifikat
              terverifikasi
            </li>
          </ul>
        </div>
      </section>
    {:else if error}
      <p class="alert-error mt-4">{error}</p>
    {/if}

    {#if progressError && !error}
      <p class="alert-info mt-4" role="status" aria-live="polite">
        <Icon name="circle-info" size="12px" class="mt-0.5 flex-none" />
        {progressError}
      </p>
    {/if}

    {#if loading}
      <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {#each Array(4) as _}<div class="skeleton h-24"></div>{/each}
      </div>
      <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each Array(6) as _}<div class="skeleton h-44"></div>{/each}
      </div>
    {:else if user && subjects.length === 0}
      <EmptyState
        icon="book-open"
        title="Belum ada pelajaran"
        description={user
          ? "Guru belum menambahkan pelajaran untuk kelasmu."
          : "Masuk untuk melihat pelajaran kelasmu."}
      />
    {:else if user}
      <!-- Overview metrics -->
      <MetricStrip
        metrics={[
          { label: "Pelajaran", value: subjects.length },
          { label: "Total Materi", value: totalLessons },
          { label: "Materi Selesai", value: completedLessons, tone: "text-mint" },
          {
            label: "Progres Belajar",
            value: `${overallPct}%`,
            tone: "text-highlight",
            role: "overall-pct",
            sub: finishedCourses > 0 ? `${finishedCourses} pelajaran tuntas` : undefined,
          },
        ]}
      />

      <!-- Search & filters -->
      <div class="mt-6 flex flex-wrap items-center gap-3">
        <SearchInput
          bind:value={query}
          placeholder="Cari pelajaran, mata pelajaran, atau guru…"
          label="Cari pelajaran"
        />
        {#if classes.length > 1}
          <select class="input !w-auto" bind:value={classFilter} aria-label="Filter kelas">
            <option value="all">Semua kelas</option>
            {#each classes as c}<option value={c}>{c}</option>{/each}
          </select>
        {/if}
        {#if subjectOptions.length > 1}
          <select
            class="input !w-auto"
            bind:value={subjectFilter}
            aria-label="Filter mata pelajaran"
          >
            <option value="all">Semua mapel</option>
            {#each subjectOptions as s}<option value={s}>{s}</option>{/each}
          </select>
        {/if}
        <select class="input !w-auto" bind:value={sortBy} aria-label="Urutkan">
          <option value="recent">Terbaru</option>
          <option value="progress">Progres tertinggi</option>
          <option value="lessons">Materi terbanyak</option>
          <option value="title">Judul (A-Z)</option>
        </select>
      </div>

      {#if filtered.length === 0}
        <EmptyState
          icon="book-open"
          title="Tidak ada pelajaran yang cocok"
          description="Coba ubah pencarian atau filtermu."
          actionLabel="Reset Filter"
          onAction={resetFilters}
        />
      {:else}
        <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {#each paged as s, i (s.id)}
            {@const prog = courseProgress(s)}
            <a
              href={`/courses/${s.id}`}
              use:reveal={{ delay: i * 40 }}
              class="card lift flex flex-col"
              data-course={s.id}
            >
              <div class="flex items-center justify-between">
                <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
                  <Icon name="book-open-reader" size="17px" />
                </span>
                <span class="badge badge-indigo"
                  >{s.class_code ?? "UMUM"}{s.class_type ? ` · ${s.class_type}` : ""}</span
                >
              </div>
              <h2 class="mt-3 font-display text-lg font-bold">{s.title}</h2>
              {#if s.subject}<p class="mono-label mt-1">{s.subject}</p>{/if}
              <p class="mt-2 line-clamp-2 flex-1 text-sm muted">
                {s.description ?? "Tanpa deskripsi"}
              </p>

              <!-- Course progress -->
              {#if prog.total > 0}
                <div class="mt-3">
                  <div class="flex items-center justify-between text-xs">
                    <span class="muted">Progres</span>
                    <span class="mono">{prog.done}/{prog.total}</span>
                  </div>
                  <div
                    class="mt-1.5 h-1.5 w-full overflow-hidden rounded-full"
                    style="background: rgb(var(--line))"
                    role="progressbar"
                    aria-valuenow={prog.done}
                    aria-valuemin={0}
                    aria-valuemax={prog.total}
                    aria-label={`Progres ${s.title}`}
                  >
                    <div
                      class="h-full rounded-full transition-all {prog.pct >= 100
                        ? 'bg-mint'
                        : 'bg-primary'}"
                      style={`width: ${prog.pct}%`}
                    ></div>
                  </div>
                </div>
              {/if}

              <div class="mono-label mt-4 flex items-center gap-3 border-t pt-3">
                <span><Icon name="user-tie" size="10px" /> {s.owner_name ?? "Guru"}</span>
                <span>·</span>
                <span><Icon name="book" size="10px" /> {s.lesson_count ?? 0} materi</span>
                {#if prog.pct >= 100 && prog.total > 0}
                  <span class="badge badge-mint ml-auto"
                    ><Icon name="check" size="9px" /> Tuntas</span
                  >
                {/if}
              </div>
            </a>
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
</div>
