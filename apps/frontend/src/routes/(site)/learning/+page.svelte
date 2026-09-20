<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";

  let courses: Course[] = [];
  let enrolled = new Set<string>();
  let loading = true;
  let error = "";
  let busy = "";
  let loadedEnrollments = false;

  $: canManage = hasRole($auth.user, "teacher");
  $: user = $auth.user;

  async function load() {
    loading = true;
    try {
      courses = await api.get<Course[]>("/courses");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat kursus";
    } finally {
      loading = false;
    }
  }

  async function loadEnrollments() {
    if (loadedEnrollments || !user) return;
    loadedEnrollments = true;
    try {
      const mine = await api.get<{ course_id: string }[]>("/me/enrollments");
      enrolled = new Set(mine.map((m) => m.course_id));
    } catch {
      /* not signed in or unavailable — leave empty */
    }
  }

  async function enroll(course: Course) {
    busy = course.id;
    try {
      await api.post(`/courses/${course.id}/enroll`);
      enrolled = new Set([...enrolled, course.id]);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mendaftar";
    } finally {
      busy = "";
    }
  }

  onMount(load);
  // React once when the auth store resolves the current user.
  $: if (user && !loadedEnrollments) loadEnrollments();
</script>

<svelte:head><title>Pembelajaran — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Ruang Belajar</p>
      <h1 class="mt-1 font-display text-4xl font-bold">Pembelajaran</h1>
      <p class="mt-2 muted">Ikuti kursus, lacak progres, dan raih sertifikat.</p>
    </div>
    {#if canManage}
      <a href="/teacher/materials" class="btn-primary">
        <Icon name="plus" size="12px" /> Materi Baru
      </a>
    {/if}
  </div>

  {#if error}
    <p class="alert-error mt-4">{error}</p>
  {/if}

  {#if loading}
    <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {#each Array(3) as _}<div class="skeleton h-40"></div>{/each}
    </div>
  {:else if courses.length === 0}
    <div class="card mt-6 grid place-items-center py-16 text-center">
      <Icon name="book-open" size="28px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada kursus</p>
      {#if canManage}
        <a href="/teacher/materials" class="btn-primary mt-4">Unggah PDF untuk memulai</a>
      {/if}
    </div>
  {:else}
    <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {#each courses as course, i}
        <div use:reveal={{ delay: i * 40 }} class="card lift flex flex-col">
          <div class="flex items-center justify-between">
            <span class="brand-mark grid h-10 w-10 place-items-center rounded-sm">
              <Icon name="book-open-reader" size="15px" />
            </span>
            <span
              class="badge"
              class:badge-mint={course.is_published}
              class:badge-neutral={!course.is_published}
            >
              {course.is_published ? "Terbit" : "Draf"}
            </span>
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
          <div class="mt-4 border-t pt-3">
            {#if enrolled.has(course.id)}
              <a href={`/learning/${course.id}`} class="btn-secondary w-full">
                <Icon name="play" size="11px" /> Lanjutkan
              </a>
            {:else}
              <button
                class="btn-primary w-full"
                on:click={() => enroll(course)}
                disabled={busy === course.id}
              >
                {#if busy === course.id}<Icon name="spinner" spin size="11px" />{:else}<Icon
                    name="plus"
                    size="11px"
                  />{/if}
                {busy === course.id ? "Mendaftar…" : "Daftar Kursus"}
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
