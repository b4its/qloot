<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Course, Lesson, Progress } from "$lib/types";
  import Icon from "$lib/components/Icon.svelte";
  import MaterialPanel from "$lib/components/MaterialPanel.svelte";

  let course: Course | null = null;
  let courseLessons: Lesson[] = [];
  let lesson: Lesson | null = null;
  let progress: Progress[] = [];
  let loading = true;
  let error = "";
  let saving = false;
  let saved = false;

  const courseId = $page.params.courseId;
  const lessonId = $page.params.lessonId;

  async function load() {
    try {
      lesson = await api.get<Lesson>(`/lessons/${lessonId}`);
      if (courseId) {
        course = await api.get<Course>(`/courses/${courseId}`).catch(() => null);
        courseLessons = await api.get<Lesson[]>(`/courses/${courseId}/lessons`).catch(() => []);
      }
      // Scope the progress query to this course (no client-side over-fetch).
      const courseIdForProgress = courseId || lesson?.course_id;
      const myProgress = courseIdForProgress
        ? await api
            .get<Progress[]>(`/me/learning-progress?course_id=${courseIdForProgress}&limit=200`)
            .catch(() => [])
        : await api.get<Progress[]>("/me/learning-progress?limit=200").catch(() => []);
      progress = myProgress;
      saved = !!myProgress.find((p) => p.lesson_id === lessonId)?.completed;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat materi";
    } finally {
      loading = false;
    }
  }

  async function toggleComplete() {
    if (!lesson) return;
    error = "";
    saving = true;
    const nextState = !saved;
    try {
      await api.post(`/lessons/${lesson.id}/progress`, {
        progress_percent: nextState ? 100 : 0,
        completed: nextState,
      });
      saved = nextState;
      // Keep the local progress list in step so the mini-bar updates.
      const others = progress.filter((p) => p.lesson_id !== lessonId);
      progress = [
        ...others,
        {
          id: `local-${lesson.id}`,
          lesson_id: lesson.id,
          course_id: lesson.course_id,
          progress_percent: nextState ? 100 : 0,
          completed: nextState,
        },
      ];
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui status materi";
    } finally {
      saving = false;
    }
  }

  function onSelectLesson(e: Event) {
    const id = (e.currentTarget as HTMLSelectElement).value;
    if (lesson) void goto(`/learning/${lesson.course_id}/lesson/${id}`);
  }

  $: currentIndex = courseLessons.findIndex((l) => l.id === lessonId);
  $: prevLesson = currentIndex > 0 ? courseLessons[currentIndex - 1] : null;
  $: nextLesson =
    currentIndex >= 0 && currentIndex < courseLessons.length - 1
      ? courseLessons[currentIndex + 1]
      : null;

  // --- course progress context -----------------------------------------------
  $: completedIds = new Set(progress.filter((p) => p.completed).map((p) => p.lesson_id));
  $: completedCount = courseLessons.filter((l) => completedIds.has(l.id)).length;
  $: coursePct = courseLessons.length
    ? Math.round((completedCount / courseLessons.length) * 100)
    : 0;

  onMount(load);
</script>

<svelte:head><title>{lesson?.title ?? "Materi"} — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  {#if loading}
    <div class="space-y-3">
      <div class="skeleton h-6 w-40"></div>
      <div class="skeleton h-64"></div>
    </div>
  {:else if !lesson}
    <p class="alert-error">{error || "Materi tidak ditemukan."}</p>
  {:else}
    <div class="flex flex-wrap items-center justify-between gap-2">
      <a
        href={`/learning/${lesson.course_id}`}
        class="text-sm text-primary flex items-center gap-1.5 transition-colors hover:underline"
      >
        <span>←</span> Kembali ke {course?.title ?? "Silabus Kursus"}
      </a>
      {#if courseLessons.length > 0 && currentIndex >= 0}
        <div class="flex items-center gap-2">
          <span class="badge surface border text-xs font-mono">
            Materi {currentIndex + 1} dari {courseLessons.length}
          </span>
          <select
            class="input !py-1 text-xs w-auto max-w-[220px]"
            value={lesson.id}
            on:change={onSelectLesson}
            aria-label="Pilih materi"
          >
            {#each courseLessons as l, i (l.id)}
              <option value={l.id}>{i + 1}. {l.title}</option>
            {/each}
          </select>
        </div>
      {/if}
    </div>

    <!-- Course progress mini-bar -->
    {#if courseLessons.length > 0}
      <div class="mt-3 flex items-center gap-3">
        <div
          class="h-1.5 flex-1 overflow-hidden rounded-full"
          style="background: rgb(var(--line))"
          role="progressbar"
          aria-valuenow={completedCount}
          aria-valuemin={0}
          aria-valuemax={courseLessons.length}
          aria-label="Progres kursus"
        >
          <div
            class="h-full rounded-full transition-all {coursePct === 100
              ? 'bg-mint'
              : 'bg-primary'}"
            style={`width: ${coursePct}%`}
          ></div>
        </div>
        <span class="mono-label text-[10px] flex-none"
          >{completedCount}/{courseLessons.length} · {coursePct}%</span
        >
      </div>
    {/if}

    <article class="card mt-3">
      <div class="flex flex-wrap items-center justify-between gap-2 border-b pb-3">
        <div class="flex items-center gap-2">
          <p class="mono-label">Materi Pembelajaran</p>
          {#if lesson.video_url}
            <span class="badge border-secondary/30 text-secondary text-[10px]">
              <Icon name="video" size="9px" /> Video
            </span>
          {/if}
        </div>
        {#if saved}
          <span class="badge badge-mint text-xs flex items-center gap-1">
            <Icon name="check" size="11px" /> Selesai Dipelajari
          </span>
        {/if}
      </div>

      <h1 class="mt-3 font-display text-2xl sm:text-3xl font-bold">{lesson.title}</h1>
      {#if lesson.video_url}
        <video class="mt-4 w-full rounded-sm border bg-black" controls src={lesson.video_url}>
          <track kind="captions" label="Captions" />
        </video>
      {/if}
      {#if lesson.content_md}
        <pre
          class="mt-4 whitespace-pre-wrap font-sans text-sm leading-relaxed">{lesson.content_md}</pre>
      {:else}
        <p class="mt-4 muted">Belum ada konten teks pada materi ini.</p>
      {/if}

      {#if error}
        <p class="alert-error mt-4">{error}</p>
      {/if}
    </article>

    <MaterialPanel lessonId={lesson.id} />

    <!-- Completion status card -->
    <article class="card mt-4">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 class="hud font-display text-base font-bold">Status Pengerjaan</h2>
          <p class="text-xs muted mt-0.5">
            {saved
              ? "Materi ini sudah ditandai selesai. Anda bisa melanjutkan ke materi berikutnya."
              : "Tandai selesai setelah Anda memahami isi materi ini untuk mencatat progres kursus."}
          </p>
        </div>

        <button
          type="button"
          class={saved ? "btn-secondary text-xs !py-1.5" : "btn-primary text-xs !py-1.5"}
          on:click={toggleComplete}
          disabled={saving}
        >
          {#if saving}<Icon name="spinner" spin size="12px" />{/if}
          <span>{saved ? "Batal Tandai Selesai" : "Tandai Selesai"}</span>
        </button>
      </div>

      {#if saved}
        <div
          class="mt-4 rounded-sm border border-mint/40 bg-mint/10 p-3 text-xs text-mint flex flex-wrap items-center justify-between gap-2"
        >
          <div class="flex items-center gap-1.5">
            <Icon name="circle-check" size="14px" />
            <span>Materi telah selesai Anda pelajari.</span>
          </div>
          {#if nextLesson}
            <a
              href={`/learning/${lesson.course_id}/lesson/${nextLesson.id}`}
              class="btn-primary !py-1 !px-2.5 text-xs"
            >
              Lanjut: {nextLesson.title} →
            </a>
          {:else}
            <a href="/certificates" class="btn-primary !py-1 !px-2.5 text-xs">
              Lihat Sertifikat Kelulusan →
            </a>
          {/if}
        </div>
      {/if}
    </article>

    <!-- Bottom Lesson Navigation -->
    {#if courseLessons.length > 0}
      <div class="mt-4 flex flex-wrap items-center justify-between gap-2">
        {#if prevLesson}
          <a
            href={`/learning/${lesson.course_id}/lesson/${prevLesson.id}`}
            class="btn-ghost text-xs flex items-center gap-1.5"
          >
            <span>←</span>
            {prevLesson.title}
          </a>
        {:else}
          <div class="text-xs muted italic">Ini adalah materi pertama</div>
        {/if}

        {#if nextLesson}
          <a
            href={`/learning/${lesson.course_id}/lesson/${nextLesson.id}`}
            class="btn-secondary text-xs flex items-center gap-1.5"
          >
            {nextLesson.title} <span>→</span>
          </a>
        {:else}
          <a
            href={`/learning/${lesson.course_id}`}
            class="btn-secondary text-xs flex items-center gap-1.5"
          >
            Selesai Kursus (Kembali ke Silabus) <span>→</span>
          </a>
        {/if}
      </div>
    {/if}
  {/if}
</div>
