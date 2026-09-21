<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let exams: Exam[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    try {
      exams = await api.get<Exam[]>(`/exams?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = exams.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
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

  async function togglePublish(exam: Exam) {
    error = "";
    message = "";
    busy = `p-${exam.id}`;
    try {
      if (exam.is_active) await api.post(`/exams/${exam.id}/close`);
      else await api.post(`/exams/${exam.id}/publish`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah status";
    } finally {
      busy = "";
    }
  }

  async function removeExam(exam: Exam) {
    if (!confirm(`Hapus ujian "${exam.title}"?`)) return;
    error = "";
    message = "";
    busy = `d-${exam.id}`;
    try {
      await api.delete(`/exams/${exam.id}`);
      message = "Ujian dihapus.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus ujian";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Ujian — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Ujian"
    title="Ujian"
    subtitle="Buat ujian, kelola soal, publikasikan, dan lihat hasil peserta."
    backHref="/teacher"
    backLabel="Panel Guru"
    actionHref="/teacher/exams/new"
    actionLabel="Ujian baru"
  />

  <PageAlerts {message} {error} />

  {#if loading}
    <div class="mt-6 space-y-3">
      {#each Array(3) as _}<div class="skeleton h-24"></div>{/each}
    </div>
  {:else if exams.length === 0}
    <div class="card mt-6 grid place-items-center py-12 text-center">
      <Icon name="file-pen" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada ujian</p>
      <p class="text-sm muted">Buat ujian pertama untuk kelasmu.</p>
      <a href="/teacher/exams/new" class="btn-primary mt-4">
        <Icon name="plus" size="12px" /> Buat ujian
      </a>
    </div>
  {:else}
    <div class="mt-6 space-y-3">
      {#each exams as exam (exam.id)}
        <div class="card flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="font-display text-lg font-bold">
              {exam.title}
              <span
                class="badge ml-1"
                class:badge-mint={exam.is_active}
                class:badge-neutral={!exam.is_active}
              >
                {exam.is_active ? "Aktif" : "Draf"}
              </span>
            </h2>
            <p class="text-sm muted">
              {exam.questions?.length ?? 0} soal · {exam.duration_minutes} menit · lulus {(
                exam.passing_score_bp / 100
              ).toFixed(0)}%
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <a href={`/teacher/exams/${exam.id}`} class="btn-ghost">
              <Icon name="pen" size="12px" /> Kelola
            </a>
            <a href={`/teacher/exams/${exam.id}/results`} class="btn-ghost">
              <Icon name="chart-simple" size="12px" /> Hasil
            </a>
            <button
              class="btn-secondary"
              on:click={() => togglePublish(exam)}
              disabled={busy === `p-${exam.id}`}
            >
              {exam.is_active ? "Tutup" : "Terbitkan"}
            </button>
            <button
              class="btn-icon !text-tertiary hover:!border-tertiary"
              on:click={() => removeExam(exam)}
              disabled={busy === `d-${exam.id}`}
              aria-label="Hapus ujian"
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
    label="ujian"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>
