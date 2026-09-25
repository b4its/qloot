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

  async function markComplete(lesson: Lesson) {
    error = "";
    busy = lesson.id;
    try {
      await api.post(`/lessons/${lesson.id}/progress`, { progress_percent: 100, completed: true });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menandai selesai";
    } finally {
      busy = "";
    }
  }

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
    <a href="/learning" class="text-sm text-primary">← Kembali ke pelajaran</a>
    <p class="mono-label mt-4">Pelajaran</p>
    <h1 class="mt-2 font-display text-3xl font-bold">{course.title}</h1>
    <p class="mt-1 muted">{course.description}</p>

    {#if courseProgress}
      <div class="card mt-4">
        <div class="flex items-center justify-between">
          <p class="mono-label">Progres</p>
          <span class="font-mono text-sm"
            >{courseProgress.completed_lessons}/{courseProgress.total_lessons} ·
            {courseProgress.percent}%</span
          >
        </div>
        <div class="track mt-2 h-1.5">
          <span style={`width:${courseProgress.percent}%`}></span>
        </div>
        {#if courseProgress.next_lesson_id}
          <a
            class="btn-primary mt-3 !py-1.5"
            href={`/learning/${courseId}/lesson/${courseProgress.next_lesson_id}`}
          >
            Lanjutkan: {courseProgress.next_lesson_title ?? "pelajaran berikutnya"}
          </a>
        {/if}
      </div>
    {/if}

    <div class="mt-6 space-y-3">
      {#each lessons as lesson, i}
        {@const done = progress[lesson.id]?.completed}
        <div class="card flex items-center justify-between">
          <div>
            <a
              href={`/learning/${course.id}/lesson/${lesson.id}`}
              class="font-medium transition-colors hover:text-primary"
            >
              {i + 1}. {lesson.title}
            </a>
            <p class="text-xs muted">{done ? "Selesai" : "Belum dimulai"}</p>
          </div>
          {#if done}
            <span class="badge badge-mint"><Icon name="check" size="10px" /> Selesai</span>
          {:else}
            <button class="btn-ghost" on:click={() => markComplete(lesson)}>Tandai selesai</button>
          {/if}
        </div>
      {/each}
      {#if lessons.length === 0}
        <p class="muted">Belum ada pelajaran di kursus ini.</p>
      {/if}
    </div>
  {/if}
</div>
