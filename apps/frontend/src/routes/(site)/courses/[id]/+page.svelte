<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Course, Lesson, Certificate } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import CertificateBadge from "$lib/components/CertificateBadge.svelte";

  let course: Course | null = null;
  let lessons: Lesson[] = [];
  let certificate: Certificate | null = null;
  let loading = true;
  let error = "";

  $: id = $page.params.id;
  $: canManage = hasRole($auth.user, "teacher");
  $: totalMinutes = lessons.length * 20;

  async function load() {
    loading = true;
    error = "";
    try {
      course = await api.get<Course>(`/courses/${id}`);
      lessons = await api.get<Lesson[]>(`/courses/${id}/lessons`);
      // If the student has earned a certificate for this course, show it.
      if (!$auth.loading && $auth.user && !canManage) {
        const mine = await api.get<Certificate[]>("/certificates").catch(() => []);
        certificate = mine.find((c) => c.course_id === id) ?? null;
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>{course ? course.title : "Pelajaran"} — QLoot</title></svelte:head>

{#if loading}
  <div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
    <div class="skeleton h-40"></div>
  </div>
{:else if error || !course}
  <div class="mx-auto max-w-xl px-4 py-24 text-center">
    <Icon name="lock" size="30px" class="muted" />
    <h1 class="mt-4 font-display text-2xl font-bold">Pelajaran tidak dapat diakses</h1>
    <p class="mt-2 muted">{error || "Pelajaran ini bukan untuk kelasmu."}</p>
    <a href="/courses" class="btn-primary mt-6">Kembali ke daftar</a>
  </div>
{:else}
  <section class="relative overflow-hidden border-b">
    <div class="aurora"></div>
    <div
      class="relative z-10 mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_340px]"
    >
      <div>
        <div class="flex items-center gap-2 text-xs muted">
          <a href="/courses" class="hover:text-primary">Pelajaran</a>
          <Icon name="chevron-right" size="9px" />
          <span>{course.class_code}{course.class_type ? ` · ${course.class_type}` : ""}</span>
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-2">
          {#if course.subject}<span class="badge badge-indigo">{course.subject}</span>{/if}
          <span class="badge badge-neutral">Kelas {course.class_code}</span>
          {#if course.class_type}<span class="badge badge-neutral">{course.class_type}</span>{/if}
        </div>
        <h1 class="mt-4 font-display text-3xl font-bold leading-tight sm:text-4xl">
          {course.title}
        </h1>
        <p class="mt-3 max-w-2xl text-ink2">
          {course.description ?? "Pelajaran ini belum memiliki deskripsi."}
        </p>

        <div class="mt-5 flex flex-wrap items-center gap-4 text-sm muted">
          <span class="inline-flex items-center gap-1.5"
            ><Icon name="user-tie" size="12px" /> {course.owner_name ?? "Guru"}</span
          >
          <span class="inline-flex items-center gap-1.5"
            ><Icon name="book" size="12px" /> {lessons.length} materi</span
          >
          <span class="inline-flex items-center gap-1.5"
            ><Icon name="clock" size="12px" /> ± {totalMinutes} menit</span
          >
        </div>
      </div>

      <div class="lg:sticky lg:top-28 h-fit">
        <div class="card">
          <div
            class="grid h-32 place-items-center rounded-sm"
            style="background-image:linear-gradient(135deg,rgba(252,238,10,.15),rgba(0,240,255,.15))"
          >
            <Icon name="book-open-reader" size="30px" class="text-primary/70" />
          </div>
          <ul class="mt-4 space-y-2 text-sm">
            <li class="flex items-center gap-2">
              <Icon name="video" class="text-primary" size="12px" />
              {lessons.length} materi pelajaran
            </li>
            <li class="flex items-center gap-2">
              <Icon name="certificate" class="text-primary" size="12px" /> Sertifikat digital
            </li>
            <li class="flex items-center gap-2">
              <Icon name="infinity" class="text-primary" size="12px" /> Akses selama kelas aktif
            </li>
            <li class="flex items-center gap-2">
              <Icon name="chalkboard-user" class="text-primary" size="12px" /> Untuk Kelas {course.class_code}
            </li>
          </ul>
          {#if lessons.length}
            <a href={`/learning/${course.id}`} class="btn-primary mt-4 w-full">
              <Icon name="play" size="12px" /> Mulai Belajar
            </a>
          {:else}
            <p class="mt-4 text-sm muted">Guru belum menambahkan materi.</p>
          {/if}
          {#if canManage}
            <a href="/teacher" class="btn-secondary mt-2 w-full"
              ><Icon name="pen" size="12px" /> Kelola Pelajaran</a
            >
          {/if}
        </div>
      </div>
    </div>
  </section>

  <div class="mx-auto max-w-7xl px-4 py-10 sm:px-6">
    <h2 class="font-display text-xl font-bold">Materi pelajaran</h2>
    {#if lessons.length === 0}
      <div class="card mt-4 grid place-items-center py-12 text-center">
        <Icon name="folder-open" size="24px" class="muted" />
        <p class="mt-2 text-sm muted">Belum ada materi untuk pelajaran ini.</p>
      </div>
    {:else}
      <ol class="mt-4 card !p-0 divide-y">
        {#each lessons as l, i}
          <li>
            <a
              href={`/learning/${course.id}/lesson/${l.id}`}
              class="flex items-center justify-between px-5 py-4 hover:bg-ink/5"
            >
              <span class="flex items-center gap-3">
                <span class="mono-label">{String(i + 1).padStart(2, "0")}</span>
                <span class="font-medium">{l.title}</span>
              </span>
              <Icon name="chevron-right" size="12px" class="muted" />
            </a>
          </li>
        {/each}
      </ol>
    {/if}

    <div class="mt-8 grid gap-6 lg:grid-cols-2">
      <div class="card">
        <h2 class="font-display text-lg font-bold">Sertifikat digital</h2>
        {#if certificate}
          <p class="mt-2 text-sm muted">
            Selamat! Kamu telah menyelesaikan pelajaran ini dan meraih sertifikat digital dengan ID
            unik dan tautan verifikasi.
          </p>
          <a href="/certificates" class="btn-secondary mt-3"
            ><Icon name="certificate" size="12px" /> Lihat sertifikat</a
          >
        {:else}
          <p class="mt-2 text-sm muted">
            Setelah menyelesaikan seluruh materi, kamu menerima sertifikat dengan ID unik dan tautan
            verifikasi.
          </p>
        {/if}
      </div>
      {#if certificate}
        <CertificateBadge
          title={certificate.course_title}
          subtitle={certificate.recipient_name}
          edition={`#${String(certificate.edition_number).padStart(4, "0")} / ${certificate.edition_total}`}
          icon="certificate"
        />
      {:else}
        <div class="card grid place-items-center text-center">
          <Icon name="lock" size="22px" class="muted" />
          <p class="mt-2 text-sm font-semibold">Sertifikat terkunci</p>
          <p class="mt-1 text-xs muted">Selesaikan semua materi untuk membukanya.</p>
        </div>
      {/if}
    </div>
  </div>
{/if}
