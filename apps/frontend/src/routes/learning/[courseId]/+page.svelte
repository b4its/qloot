<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Course, Lesson, Progress } from "$lib/types";

  let course: Course | null = null;
  let lessons: Lesson[] = [];
  let progress: Record<string, Progress> = {};
  let loading = true;
  let error = "";

  const courseId = $page.params.courseId;

  async function load() {
    loading = true;
    try {
      course = await api.get<Course>(`/courses/${courseId}`);
      lessons = await api.get<Lesson[]>(`/courses/${courseId}/lessons`);
      const all = await api.get<Progress[]>("/me/learning-progress");
      progress = Object.fromEntries(
        all.filter((p) => p.course_id === courseId).map((p) => [p.lesson_id, p]),
      );
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load course";
    } finally {
      loading = false;
    }
  }

  async function markComplete(lesson: Lesson) {
    await api.post(`/lessons/${lesson.id}/progress`, { progress_percent: 100, completed: true });
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>{course?.title ?? "Course"} — QLoot</title></svelte:head>

{#if loading}
  <p class="muted">Loading…</p>
{:else if error}
  <p class="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{:else if course}
  <a href="/learning" class="text-sm text-primary-600">← Back to courses</a>
  <h1 class="mt-2 text-2xl font-bold">{course.title}</h1>
  <p class="mt-1 muted">{course.description}</p>

  <div class="mt-6 space-y-3">
    {#each lessons as lesson, i}
      {@const done = progress[lesson.id]?.completed}
      <div class="card flex items-center justify-between">
        <div>
          <a
            href={`/learning/${course.id}/lesson/${lesson.id}`}
            class="font-medium hover:text-primary-600"
          >
            {i + 1}. {lesson.title}
          </a>
          <p class="text-xs muted">{done ? "Completed" : "Not started"}</p>
        </div>
        {#if done}
          <span class="badge bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-100"
            >✓ Done</span
          >
        {:else}
          <button class="btn-ghost" on:click={() => markComplete(lesson)}>Mark complete</button>
        {/if}
      </div>
    {/each}
    {#if lessons.length === 0}
      <p class="muted">No lessons in this course yet.</p>
    {/if}
  </div>
{/if}
