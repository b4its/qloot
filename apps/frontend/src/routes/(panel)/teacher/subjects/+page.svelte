<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  // Redirect once auth resolves; a mount-only check could fire before the
  // session loaded, briefly exposing teacher-only UI.
  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let subjects: Course[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    error = "";
    try {
      subjects = await api.get<Course[]>(`/courses?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = subjects.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    page = next;
    load();
  }

  async function remove(s: Course) {
    if (!confirm(`Hapus pelajaran "${s.title}"?`)) return;
    error = "";
    message = "";
    busy = `d-${s.id}`;
    try {
      await api.delete(`/courses/${s.id}`);
      message = "Pelajaran dihapus.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus";
    } finally {
      busy = "";
    }
  }

  async function togglePublish(s: Course) {
    error = "";
    message = "";
    busy = `p-${s.id}`;
    try {
      await api.patch(`/courses/${s.id}`, { is_published: !s.is_published });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Pelajaran — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Pelajaran"
    title="Pelajaran"
    subtitle="Kelola pelajaran yang kamu ampu. Siswa di kelas yang ditargetkan otomatis dapat mengaksesnya."
    backHref="/teacher"
    backLabel="Panel Guru"
    actionHref="/teacher/subjects/new"
    actionLabel="Pelajaran baru"
  />

  <PageAlerts {message} {error} />

  {#if loading}
    <div class="mt-6 space-y-3">
      {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
    </div>
  {:else if subjects.length === 0}
    <div class="card mt-6 grid place-items-center py-14 text-center">
      <Icon name="chalkboard-user" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada pelajaran</p>
      <p class="text-sm muted">Buat pelajaran pertama untuk kelasmu.</p>
      <a href="/teacher/subjects/new" class="btn-primary mt-4">
        <Icon name="plus" size="12px" /> Buat pelajaran
      </a>
    </div>
  {:else}
    <div class="card mt-6 !p-0 divide-y">
      {#each subjects as s}
        <div class="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div class="flex items-center gap-4">
            <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
              <Icon name="book-open-reader" size="17px" />
            </span>
            <div>
              <div class="flex flex-wrap items-center gap-2">
                <p class="font-semibold">{s.title}</p>
                <span class="badge badge-indigo"
                  >Kelas {s.class_code}{s.class_type ? ` · ${s.class_type}` : ""}</span
                >
                {#if !s.is_published}<span class="badge badge-amber">Draf</span>{/if}
              </div>
              <p class="text-xs muted">
                {s.subject ?? "Tanpa mata pelajaran"} · {s.lesson_count ?? 0} materi
              </p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <a href={`/teacher/subjects/${s.id}`} class="btn-ghost">
              <Icon name="pen" size="12px" /> Kelola
            </a>
            <button
              class="btn-secondary"
              on:click={() => togglePublish(s)}
              disabled={busy === `p-${s.id}`}
            >
              <Icon name={s.is_published ? "eye-slash" : "upload"} size="12px" />
              {s.is_published ? "Sembunyikan" : "Terbitkan"}
            </button>
            <button
              class="btn-icon !text-tertiary hover:!border-tertiary"
              on:click={() => remove(s)}
              disabled={busy === `d-${s.id}`}
              aria-label="Hapus"
            >
              <Icon name="trash" size="12px" />
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <Pagination
    {page}
    pageSize={PAGE}
    {hasMore}
    {loading}
    label="pelajaran"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>
