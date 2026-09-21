<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Course, Progress } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import { paginate } from "$lib/utils/format";
  import { reveal } from "$lib/actions/reveal";

  const PAGE_SIZE = 9;
  let courses: Course[] = [];
  let progress: Progress[] = [];
  let loading = true;
  let error = "";
  let currentPage = 1;
  // Guard so the auth-triggered reload runs at most once per resolved user —
  // otherwise a user with zero courses re-triggers load() forever (load() sets
  // loading=false while courses stays empty).
  let loadedForUser = false;

  $: canManage = hasRole($auth.user, "teacher");
  $: user = $auth.user;
  $: totalPages = Math.max(1, Math.ceil(courses.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedCourses = paginate(courses, currentPage, PAGE_SIZE);

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

<svelte:head><title>Pembelajaran — QLoot</title></svelte:head>

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
    <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {#each Array(3) as _}<div class="skeleton h-40"></div>{/each}
    </div>
  {:else if courses.length === 0}
    <div class="card mt-6 grid place-items-center py-16 text-center">
      <Icon name="book-open" size="28px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada pelajaran</p>
      <p class="mt-1 text-sm muted">
        {canManage
          ? "Buat pelajaran dan targetkan ke sebuah kelas."
          : "Pelajaran untuk kelasmu akan muncul di sini setelah gurumu menerbitkannya."}
      </p>
      {#if canManage}
        <a href="/teacher/subjects" class="btn-primary mt-4">Buat Pelajaran</a>
      {/if}
    </div>
  {:else}
    <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {#each pagedCourses as course, i}
        {@const status = courseStatus(course)}
        {@const done = doneByCourse[course.id] ?? 0}
        {@const total = course.lesson_count ?? 0}
        <div use:reveal={{ delay: i * 40 }} class="card lift flex flex-col">
          <div class="flex items-center justify-between">
            <span class="tile h-10 w-10">
              <Icon name="book-open-reader" size="15px" />
            </span>
            {#if status === "done"}
              <span class="badge badge-mint"><Icon name="circle-check" size="10px" /> Selesai</span>
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
              <div class="track h-1.5">
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
      total={courses.length}
      {loading}
      label="pelajaran"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>
