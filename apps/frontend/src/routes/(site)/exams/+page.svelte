<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import { paginate } from "$lib/utils/format";
  import { reveal } from "$lib/actions/reveal";
  import { formatDate } from "$lib/utils/format";

  const PAGE_SIZE = 10;
  let exams: Exam[] = [];
  let loading = true;
  let error = "";
  let currentPage = 1;
  $: canManage = hasRole($auth.user, "teacher");
  $: totalPages = Math.max(1, Math.ceil(exams.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedExams = paginate(exams, currentPage, PAGE_SIZE);

  async function load() {
    try {
      exams = await api.get<Exam[]>("/exams?limit=200");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Ujian — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Asesmen</p>
      <h1 class="mt-1 font-display text-4xl font-bold">Ujian</h1>
      <p class="mt-2 muted">Kerjakan ujian dengan timer server-authoritative dan feedback AI.</p>
    </div>
    {#if canManage}
      <a href="/teacher/exams" class="btn-primary"><Icon name="plus" size="12px" /> Kelola Ujian</a>
    {/if}
  </div>

  {#if error}
    <p class="alert-error mt-4">{error}</p>
  {/if}

  {#if loading}
    <div class="mt-6 grid gap-5 sm:grid-cols-2">
      {#each Array(2) as _}<div class="skeleton h-32"></div>{/each}
    </div>
  {:else if exams.length === 0}
    <div class="card mt-6 grid place-items-center py-16 text-center">
      <Icon name="file-pen" size="28px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada ujian</p>
      <p class="text-sm muted">Ujian yang dipublikasikan akan muncul di sini.</p>
    </div>
  {:else}
    <div class="mt-6 grid gap-5 sm:grid-cols-2">
      {#each pagedExams as exam, i}
        <a href={`/exams/${exam.id}`} use:reveal={{ delay: i * 40 }} class="card lift block">
          <div class="flex items-center justify-between">
            <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
              <Icon name="file-pen" size="17px" />
            </span>
            <span
              class="badge"
              class:badge-mint={exam.is_active}
              class:badge-neutral={!exam.is_active}
            >
              <Icon name={exam.is_active ? "lock-open" : "lock"} size="9px" />
              {exam.is_active ? "terbuka" : exam.status}
            </span>
          </div>
          <h2 class="mt-3 font-display text-lg font-bold">{exam.title}</h2>
          <div class="mono-label mt-2 flex flex-wrap items-center gap-3">
            <span><Icon name="clock" size="10px" /> {exam.duration_minutes} menit</span>
            <span>·</span>
            <span
              ><Icon name="bullseye" size="10px" /> lulus {(exam.passing_score_bp / 100).toFixed(
                0,
              )}%</span
            >
          </div>
          {#if exam.opens_at}<p class="mt-2 text-xs muted">
              Mulai {formatDate(exam.opens_at)}
            </p>{/if}
        </a>
      {/each}
    </div>
    <Pagination
      page={currentPage}
      pageSize={PAGE_SIZE}
      total={exams.length}
      {loading}
      label="ujian"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>
