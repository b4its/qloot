<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import FilterChips from "$lib/components/FilterChips.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Course, Lesson, Progress } from "$lib/types";

  let course: Course | null = null;
  let lessons: Lesson[] = [];
  let progress: Record<string, Progress> = {};
  // Aggregate course progress + resume pointer (C37).
  let courseProgress: {
    percent: number;
    completed_lessons: number;
    total_lessons: number;
    next_lesson_id: string | null;
    next_lesson_title: string | null;
  } | null = null;
  let loading = true;
  let error = "";
  let progressLoading = false;
  let progressError = "";
  let progressLoaded = false;
  let actionError = "";
  let busy = "";
  let searchQuery = "";
  let filterStatus: "all" | "completed" | "uncompleted" = "all";

  const courseId = $page.params.courseId;

  const filterOptions = [
    ["all", "Semua"],
    ["completed", "Selesai"],
    ["uncompleted", "Belum"],
  ] as const;

  async function loadProgress() {
    progressLoading = true;
    progressError = "";
    try {
      const [aggregate, mine] = await Promise.all([
        api.get<typeof courseProgress>(`/courses/${courseId}/progress`),
        api.get<Progress[]>(`/me/learning-progress?course_id=${courseId}&limit=200`),
      ]);
      courseProgress = aggregate;
      progress = Object.fromEntries(mine.map((p) => [p.lesson_id, p]));
      progressLoaded = true;
    } catch (e) {
      progressError = e instanceof ApiError ? e.message : "Progres belajar belum dapat dimuat";
      progressLoaded = false;
      courseProgress = null;
      progress = {};
      filterStatus = "all";
    } finally {
      progressLoading = false;
    }
  }

  async function load() {
    loading = true;
    error = "";
    try {
      [course, lessons] = await Promise.all([
        api.get<Course>(`/courses/${courseId}`),
        api.get<Lesson[]>(`/courses/${courseId}/lessons`),
      ]);
      await loadProgress();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
    } finally {
      loading = false;
    }
  }

  async function toggleComplete(lesson: Lesson) {
    actionError = "";
    busy = lesson.id;
    const isDone = !!progress[lesson.id]?.completed;
    try {
      await api.post(`/lessons/${lesson.id}/progress`, {
        progress_percent: isDone ? 0 : 100,
        completed: !isDone,
      });
      await loadProgress();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : "Gagal mengubah status materi";
    } finally {
      busy = "";
    }
  }

  $: completedCount = progressLoaded
    ? lessons.filter((l) => !!progress[l.id]?.completed).length
    : null;
  $: filteredLessons = lessons.filter((l) => {
    const matchesSearch =
      !searchQuery.trim() || l.title.toLowerCase().includes(searchQuery.trim().toLowerCase());
    const isDone = progressLoaded && !!progress[l.id]?.completed;
    if (filterStatus === "completed") return matchesSearch && isDone;
    if (filterStatus === "uncompleted") return matchesSearch && !isDone;
    return matchesSearch;
  });
  $: metrics = [
    { label: "Total Materi", value: lessons.length },
    { label: "Materi Selesai", value: completedCount ?? "—", tone: "text-mint" },
    {
      label: "Tersisa",
      value: completedCount == null ? "—" : Math.max(0, lessons.length - completedCount),
      tone: "text-primary",
    },
    {
      label: "Kelulusan",
      value: courseProgress ? `${courseProgress.percent}%` : "—",
      tone: courseProgress?.percent === 100 ? "text-mint" : undefined,
    },
  ];

  onMount(load);
</script>

<svelte:head><title>{course?.title ?? "Pelajaran"} — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  {#if loading}
    <Skeleton rows={4} />
  {:else if error}
    <div class="space-y-3">
      <p class="alert-error" role="alert" aria-live="assertive">
        {error}
      </p>
      <button class="btn-secondary" on:click={load}>
        <Icon name="rotate" size="12px" /> Coba lagi
      </button>
    </div>
  {:else if course}
    <a
      href="/learning"
      class="text-sm text-primary flex items-center gap-1.5 transition-colors hover:underline"
    >
      <span>←</span> Kembali ke katalog pelajaran
    </a>
    <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="mono-label">Silabus Kursus</p>
        <h1 class="mt-1 font-display text-3xl font-bold">{course.title}</h1>
      </div>
      {#if courseProgress && courseProgress.percent === 100}
        <a
          href="/certificates"
          class="badge badge-mint !py-1 !px-3 text-xs flex items-center gap-1.5"
        >
          <Icon name="award" size="14px" />
          <span>Sertifikat Siap Dilihat</span>
        </a>
      {/if}
    </div>
    <p class="mt-2 text-sm muted leading-relaxed">{course.description}</p>

    <!-- Metrics overview -->
    <MetricStrip {metrics} />

    {#if progressError}
      <div
        class="alert-warning mt-4 flex flex-wrap items-center justify-between gap-3"
        role="status"
      >
        <span>
          <strong>Materi tetap dapat dibuka.</strong>
          {progressError}; status selesai untuk sementara tidak ditampilkan.
        </span>
        <button class="btn-ghost !py-1 text-xs" on:click={loadProgress} disabled={progressLoading}>
          <Icon name={progressLoading ? "spinner" : "rotate"} spin={progressLoading} size="11px" />
          Muat ulang progres
        </button>
      </div>
    {/if}

    {#if courseProgress}
      <div class="card mt-4">
        <div class="flex items-center justify-between">
          <p class="mono-label">Progres Pembelajaran</p>
          <span class="font-mono text-sm font-semibold"
            >{courseProgress.completed_lessons}/{courseProgress.total_lessons} Materi ·
            {courseProgress.percent}%</span
          >
        </div>
        <div
          class="track mt-2 h-2"
          role="progressbar"
          aria-label="Progres pembelajaran"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={courseProgress.percent}
        >
          <span style={`width:${courseProgress.percent}%`}></span>
        </div>
        {#if courseProgress.percent === 100}
          <div
            class="mt-4 rounded-sm border border-mint/40 bg-mint/10 p-3 text-xs text-mint flex flex-wrap items-center justify-between gap-3"
          >
            <div class="flex items-center gap-2">
              <Icon name="check" size="16px" />
              <span class="font-medium"
                >Selamat! Anda telah menyelesaikan seluruh materi kursus ini.</span
              >
            </div>
            <a href="/certificates" class="btn-primary !py-1 text-xs"> Lihat Sertifikat </a>
          </div>
        {:else if courseProgress.next_lesson_id}
          <div class="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-3">
            <div class="text-xs">
              <span class="muted">Lanjutkan dari materi terakhir: </span>
              <span class="font-medium text-foreground"
                >{courseProgress.next_lesson_title ?? "Materi berikutnya"}</span
              >
            </div>
            <a
              class="btn-primary !py-1.5 text-xs"
              href={`/learning/${courseId}/lesson/${courseProgress.next_lesson_id}`}
            >
              Lanjutkan Belajar →
            </a>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Search & Filter Controls -->
    <div class="mt-8 flex flex-wrap items-center justify-between gap-3">
      {#if progressLoaded}
        <FilterChips
          options={filterOptions.map(([value, label]) => [
            value,
            value === "all"
              ? `${label} (${lessons.length})`
              : value === "completed"
                ? `${label} (${completedCount ?? 0})`
                : `${label} (${Math.max(0, lessons.length - (completedCount ?? 0))})`,
          ])}
          bind:value={filterStatus}
          label="Filter status materi"
        />
      {/if}

      <div class="w-full sm:w-64">
        <SearchInput bind:value={searchQuery} placeholder="Cari materi..." label="Cari materi" />
      </div>
    </div>

    <!-- Lessons List -->
    <div class="mt-4 space-y-3">
      {#if actionError}
        <p class="alert-error" role="alert" aria-live="assertive">
          {actionError}
        </p>
      {/if}
      {#each filteredLessons as lesson, i}
        {@const done = progressLoaded && !!progress[lesson.id]?.completed}
        {@const isBusy = busy === lesson.id}
        <div
          class="card flex flex-wrap items-center justify-between gap-4 transition-colors hover:border-primary/40"
        >
          <div class="flex items-start gap-3 flex-1 min-w-[240px]">
            <span
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-xs font-mono text-xs font-bold {done
                ? 'bg-mint/20 text-mint border border-mint/40'
                : 'surface border border-border text-muted'}"
            >
              {i + 1}
            </span>
            <div>
              <a
                href={`/learning/${course.id}/lesson/${lesson.id}`}
                class="font-medium text-sm transition-colors hover:text-primary flex items-center gap-2"
              >
                <span>{lesson.title}</span>
              </a>
              <div class="mt-1 flex items-center gap-2 text-xs">
                {#if lesson.video_url}
                  <span class="badge border-secondary/30 text-secondary text-[10px]">
                    <Icon name="video" size="9px" /> Video
                  </span>
                {:else}
                  <span class="badge text-muted text-[10px]">
                    <Icon name="file-text" size="9px" /> Artikel
                  </span>
                {/if}
                <span class="muted">·</span>
                <span class={done ? "text-mint font-medium" : "muted"}>
                  {progressLoaded ? (done ? "Selesai" : "Belum dimulai") : "Status belum tersedia"}
                </span>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 shrink-0">
            {#if progressLoaded}
              <button
                type="button"
                class="btn-ghost !py-1 !px-2.5 text-xs flex items-center gap-1.5"
                on:click={() => toggleComplete(lesson)}
                disabled={isBusy}
                title={done ? "Tandai belum selesai" : "Tandai selesai"}
              >
                {#if isBusy}
                  <Icon name="spinner" spin size="11px" />
                {:else if done}
                  <Icon name="check" size="11px" class="text-mint" />
                {/if}
                <span>{done ? "Batal Selesai" : "Tandai Selesai"}</span>
              </button>
            {/if}
            <a
              href={`/learning/${course.id}/lesson/${lesson.id}`}
              class="btn-secondary !py-1 !px-3 text-xs"
            >
              Buka Materi →
            </a>
          </div>
        </div>
      {/each}

      {#if lessons.length === 0}
        <EmptyState
          icon="book-open"
          title="Belum ada materi pelajaran"
          description="Guru belum menerbitkan materi untuk pelajaran ini."
        />
      {:else if filteredLessons.length === 0}
        <EmptyState
          icon="magnifying-glass"
          title="Tidak ada materi yang cocok"
          description="Ubah pencarian atau filter status materi."
          actionLabel="Reset Filter"
          onAction={() => {
            searchQuery = "";
            filterStatus = "all";
          }}
        />
      {/if}
    </div>
  {/if}
</div>
