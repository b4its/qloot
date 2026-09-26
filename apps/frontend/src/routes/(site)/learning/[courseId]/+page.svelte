<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
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
  let busy = "";
  let searchQuery = "";
  let filterStatus: "all" | "completed" | "uncompleted" = "all";

  const courseId = $page.params.courseId;

  async function load() {
    loading = true;
    try {
      course = await api.get<Course>(`/courses/${courseId}`);
      lessons = await api.get<Lesson[]>(`/courses/${courseId}/lessons`);
      courseProgress = await api.get(`/courses/${courseId}/progress`);
      const all = await api.get<Progress[]>("/me/learning-progress?limit=200");
      progress = Object.fromEntries(
        all.filter((p) => p.course_id === courseId).map((p) => [p.lesson_id, p]),
      );
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
    } finally {
      loading = false;
    }
  }

  async function toggleComplete(lesson: Lesson) {
    error = "";
    busy = lesson.id;
    const isDone = !!progress[lesson.id]?.completed;
    try {
      await api.post(`/lessons/${lesson.id}/progress`, {
        progress_percent: isDone ? 0 : 100,
        completed: !isDone,
      });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah status materi";
    } finally {
      busy = "";
    }
  }

  $: completedCount = lessons.filter((l) => !!progress[l.id]?.completed).length;
  $: filteredLessons = lessons.filter((l) => {
    const matchesSearch =
      !searchQuery.trim() || l.title.toLowerCase().includes(searchQuery.trim().toLowerCase());
    const isDone = !!progress[l.id]?.completed;
    if (filterStatus === "completed") return matchesSearch && isDone;
    if (filterStatus === "uncompleted") return matchesSearch && !isDone;
    return matchesSearch;
  });

  onMount(load);
</script>

<svelte:head><title>{course?.title ?? "Pelajaran"} — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  {#if loading}
    <Skeleton rows={4} />
  {:else if error}
    <p class="alert-error">
      {error}
    </p>
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
    <div class="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
      <div class="rounded-sm border p-3 surface">
        <span class="mono-label text-[10px]">Total Materi</span>
        <p class="font-mono text-lg font-bold mt-1">{lessons.length}</p>
      </div>
      <div class="rounded-sm border p-3 surface">
        <span class="mono-label text-[10px]">Materi Selesai</span>
        <p class="font-mono text-lg font-bold text-mint mt-1">{completedCount}</p>
      </div>
      <div class="rounded-sm border p-3 surface">
        <span class="mono-label text-[10px]">Tersisa</span>
        <p class="font-mono text-lg font-bold mt-1 text-primary">
          {Math.max(0, lessons.length - completedCount)}
        </p>
      </div>
      <div class="rounded-sm border p-3 surface">
        <span class="mono-label text-[10px]">Kelulusan</span>
        <p
          class="font-mono text-lg font-bold mt-1 {courseProgress?.percent === 100
            ? 'text-mint'
            : 'muted'}"
        >
          {courseProgress?.percent ?? 0}%
        </p>
      </div>
    </div>

    {#if courseProgress}
      <div class="card mt-4">
        <div class="flex items-center justify-between">
          <p class="mono-label">Progres Pembelajaran</p>
          <span class="font-mono text-sm font-semibold"
            >{courseProgress.completed_lessons}/{courseProgress.total_lessons} Materi ·
            {courseProgress.percent}%</span
          >
        </div>
        <div class="track mt-2 h-2">
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
      <div class="flex items-center gap-1.5 rounded-sm border p-1 surface">
        <button
          type="button"
          class="px-2.5 py-1 text-xs rounded-xs font-medium transition-colors"
          class:bg-primary={filterStatus === "all"}
          class:text-[#05060A]={filterStatus === "all"}
          class:muted={filterStatus !== "all"}
          on:click={() => (filterStatus = "all")}
        >
          Semua ({lessons.length})
        </button>
        <button
          type="button"
          class="px-2.5 py-1 text-xs rounded-xs font-medium transition-colors"
          class:bg-primary={filterStatus === "completed"}
          class:text-[#05060A]={filterStatus === "completed"}
          class:muted={filterStatus !== "completed"}
          on:click={() => (filterStatus = "completed")}
        >
          Selesai ({completedCount})
        </button>
        <button
          type="button"
          class="px-2.5 py-1 text-xs rounded-xs font-medium transition-colors"
          class:bg-primary={filterStatus === "uncompleted"}
          class:text-[#05060A]={filterStatus === "uncompleted"}
          class:muted={filterStatus !== "uncompleted"}
          on:click={() => (filterStatus = "uncompleted")}
        >
          Belum ({Math.max(0, lessons.length - completedCount)})
        </button>
      </div>

      <div class="relative w-full sm:w-64">
        <input
          type="text"
          class="input text-xs !py-1.5 w-full"
          placeholder="Cari materi..."
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
    </div>

    <!-- Lessons List -->
    <div class="mt-4 space-y-3">
      {#each filteredLessons as lesson, i}
        {@const done = !!progress[lesson.id]?.completed}
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
                  {done ? "Selesai" : "Belum dimulai"}
                </span>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 shrink-0">
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
        <p class="card text-center text-sm muted py-8">Belum ada materi pelajaran di kursus ini.</p>
      {:else if filteredLessons.length === 0}
        <p class="card text-center text-sm muted py-8">
          Tidak ada materi yang sesuai dengan pencarian atau filter yang dipilih.
        </p>
      {/if}
    </div>
  {/if}
</div>
