<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Lesson } from "$lib/types";

  let lesson: Lesson | null = null;
  let loading = true;
  let error = "";
  let saving = false;

  const lessonId = $page.params.lessonId;

  async function load() {
    try {
      lesson = await api.get<Lesson>(`/lessons/${lessonId}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load lesson";
    } finally {
      loading = false;
    }
  }

  async function complete() {
    if (!lesson) return;
    saving = true;
    try {
      await api.post(`/lessons/${lesson.id}/progress`, { progress_percent: 100, completed: true });
    } finally {
      saving = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>{lesson?.title ?? "Lesson"} — QLoot</title></svelte:head>

{#if loading}
  <p class="muted">Loading…</p>
{:else if error}
  <p class="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>
{:else if lesson}
  <a href={`/learning/${lesson.course_id}`} class="text-sm text-primary-600">← Back to course</a>
  <article class="card mt-3">
    <h1 class="text-2xl font-bold">{lesson.title}</h1>
    {#if lesson.video_url}
      <video class="mt-4 w-full rounded-lg" controls src={lesson.video_url}>
        <track kind="captions" label="Captions" />
      </video>
    {/if}
    {#if lesson.content_md}
      <pre class="mt-4 whitespace-pre-wrap font-sans text-sm">{lesson.content_md}</pre>
    {:else}
      <p class="mt-4 muted">No content yet.</p>
    {/if}
    <button class="btn-primary mt-6" on:click={complete} disabled={saving}>
      {saving ? "Saving…" : "Mark as complete"}
    </button>
  </article>
{/if}
