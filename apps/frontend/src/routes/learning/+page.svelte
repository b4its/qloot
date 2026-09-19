<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";

  let courses: Course[] = [];
  let loading = true;
  let error = "";
  $: canManage = hasRole($auth.user, "teacher");

  async function load() {
    loading = true;
    try {
      courses = await api.get<Course[]>("/courses");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load courses";
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Learning — QLoot</title></svelte:head>

<div class="flex items-center justify-between">
  <h1 class="text-2xl font-bold">Learning</h1>
  {#if canManage}
    <a href="/teacher/materials" class="btn-primary">＋ New material</a>
  {/if}
</div>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-tertiary dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading courses…</p>
{:else if courses.length === 0}
  <div class="card mt-6 text-center">
    <p class="muted">No courses yet.</p>
    {#if canManage}<a href="/teacher/materials" class="btn-primary mt-3"
        >Upload a PDF to get started</a
      >{/if}
  </div>
{:else}
  <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each courses as course}
      <a href={`/learning/${course.id}`} class="card block transition hover:border-primary">
        <h2 class="font-semibold">{course.title}</h2>
        <p class="mt-1 line-clamp-2 text-sm muted">{course.description ?? "No description"}</p>
        <div class="mt-3 text-xs muted">
          {course.is_published ? "Published" : "Draft"}
        </div>
      </a>
    {/each}
  </div>
{/if}
