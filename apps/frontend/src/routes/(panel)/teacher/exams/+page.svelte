<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import FilterChips from "$lib/components/FilterChips.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";
  import { examCategory, paginate, type ExamCategory } from "$lib/utils/format";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  // Tabs: Semua, Pilihan Ganda, Esai, Campuran. Pure-MC exams live in the PG
  // tab, pure-essay in the Esai tab, and exams mixing both in Campuran.
  type Filter = "all" | "multiple_choice" | "essay" | "mixed";
  let filter: Filter = "all";
  let exams: Exam[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let deletingExam: Exam | null = null;
  let page = 1;
  let query = "";
  let statusFilter: "all" | "active" | "draft" = "all";

  $: counts = {
    all: exams.length,
    multiple_choice: exams.filter((e) => examCategory(e) === "multiple_choice").length,
    essay: exams.filter((e) => examCategory(e) === "essay").length,
    mixed: exams.filter((e) => examCategory(e) === "mixed").length,
  };
  $: activeCount = exams.filter((e) => e.is_active).length;
  $: draftCount = exams.length - activeCount;
  $: totalQuestions = exams.reduce((s, e) => s + (e.question_count ?? e.questions?.length ?? 0), 0);
  // Filter over the *whole* set (not just the current page) so tab counts and
  // category filtering are accurate, then paginate the filtered list.
  $: filteredExams = exams
    .filter((e) => filter === "all" || examCategory(e) === filter)
    .filter((e) => {
      if (statusFilter === "active" && !e.is_active) return false;
      if (statusFilter === "draft" && e.is_active) return false;
      if (query.trim() && !e.title.toLowerCase().includes(query.toLowerCase().trim())) return false;
      return true;
    });
  $: totalPages = Math.max(1, Math.ceil(filteredExams.length / PAGE));
  $: if (page > totalPages) page = 1;
  $: visibleExams = paginate(filteredExams, page, PAGE);

  const CATEGORY_BADGE: Record<ExamCategory, string> = {
    multiple_choice: "PG",
    essay: "Esai",
    mixed: "Campuran",
    empty: "-",
  };

  function selectFilter(f: Filter) {
    filter = f;
    page = 1;
  }

  function resetFilters() {
    query = "";
    statusFilter = "all";
    filter = "all";
    page = 1;
  }

  async function load() {
    loading = true;
    try {
      exams = await api.get<Exam[]>("/exams?limit=200");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    page = Math.min(totalPages, Math.max(1, page + delta));
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
    deletingExam = exam;
  }

  async function confirmRemoveExam() {
    const exam = deletingExam;
    if (!exam) return;
    deletingExam = null;
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

<svelte:head><title>Ujian | Panel Guru | QLoot</title></svelte:head>

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
    <EmptyState
      icon="file-pen"
      title="Belum ada ujian"
      description="Buat ujian pertama untuk kelasmu."
      actionHref="/teacher/exams/new"
      actionLabel="Buat ujian"
    />
  {:else}
    <!-- Overview metrics -->
    <MetricStrip
      metrics={[
        { label: "Total Ujian", value: exams.length },
        { label: "Aktif", value: activeCount, tone: "text-mint", role: "active-count" },
        { label: "Draf", value: draftCount, tone: "text-highlight" },
        { label: "Total Soal", value: totalQuestions },
      ]}
    />

    <div class="mt-6 flex flex-wrap gap-2" role="tablist" aria-label="Kategori ujian">
      <button
        class="btn-ghost !py-1.5"
        class:!border-primary={filter === "all"}
        class:!text-primary={filter === "all"}
        role="tab"
        aria-selected={filter === "all"}
        on:click={() => selectFilter("all")}
      >
        Semua <span class="mono ml-1 text-xs muted">{counts.all}</span>
      </button>
      <button
        class="btn-ghost !py-1.5"
        class:!border-primary={filter === "multiple_choice"}
        class:!text-primary={filter === "multiple_choice"}
        role="tab"
        aria-selected={filter === "multiple_choice"}
        on:click={() => selectFilter("multiple_choice")}
      >
        <Icon name="list-check" size="11px" /> Pilihan Ganda
        <span class="mono ml-1 text-xs muted">{counts.multiple_choice}</span>
      </button>
      <button
        class="btn-ghost !py-1.5"
        class:!border-primary={filter === "essay"}
        class:!text-primary={filter === "essay"}
        role="tab"
        aria-selected={filter === "essay"}
        on:click={() => selectFilter("essay")}
      >
        <Icon name="pen-fancy" size="11px" /> Esai
        <span class="mono ml-1 text-xs muted">{counts.essay}</span>
      </button>
      {#if counts.mixed}
        <button
          class="btn-ghost !py-1.5"
          class:!border-primary={filter === "mixed"}
          class:!text-primary={filter === "mixed"}
          role="tab"
          aria-selected={filter === "mixed"}
          on:click={() => selectFilter("mixed")}
        >
          <Icon name="layer-group" size="11px" /> Campuran
          <span class="mono ml-1 text-xs muted">{counts.mixed}</span>
        </button>
      {/if}
    </div>

    <!-- Search + status filter -->
    <div class="mt-3 flex flex-wrap items-center gap-2">
      <div class="w-full sm:w-64">
        <SearchInput
          bind:value={query}
          placeholder="Cari ujian..."
          label="Cari ujian"
          oninput={() => (page = 1)}
        />
      </div>
      <FilterChips
        options={[
          ["all", "Semua"],
          ["active", "Aktif"],
          ["draft", "Draf"],
        ]}
        bind:value={statusFilter}
        label="Filter status ujian"
        onchange={() => (page = 1)}
      />
    </div>

    {#if visibleExams.length === 0}
      <EmptyState
        icon="file-pen"
        title="Tidak ada ujian yang cocok"
        description="Ubah kategori, status, atau pencarianmu."
        actionLabel="Reset Filter"
        onAction={resetFilters}
      />
    {:else}
      <div class="mt-6 space-y-3">
        {#each visibleExams as exam (exam.id)}
          {@const cat = examCategory(exam)}
          <div class="card flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="font-display text-lg font-bold">
                {exam.title}
                <span
                  class="badge ml-1"
                  class:badge-indigo={cat === "multiple_choice"}
                  class:badge-magenta={cat === "essay"}
                  class:badge-neutral={cat === "mixed" || cat === "empty"}
                >
                  {CATEGORY_BADGE[cat]}
                </span>
                <span
                  class="badge ml-1"
                  class:badge-mint={exam.is_active}
                  class:badge-neutral={!exam.is_active}
                >
                  {exam.is_active ? "Aktif" : "Draf"}
                </span>
              </h2>
              <p class="text-sm muted">
                {exam.question_count ?? exam.questions?.length ?? 0} soal
                {#if cat === "multiple_choice"}
                  PG
                {:else if cat === "essay"}
                  esai
                {:else if cat === "mixed"}
                  ({exam.mc_count ?? 0} PG · {exam.essay_count ?? 0} esai)
                {/if}
                · {exam.duration_minutes} menit · lulus {(exam.passing_score_bp / 100).toFixed(0)}%
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
  {/if}

  <Pagination
    {page}
    pageSize={PAGE}
    total={filteredExams.length}
    {loading}
    label="ujian"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>

{#if deletingExam}
  <ConfirmDialog
    title="Hapus Ujian"
    description={`Ujian "${deletingExam.title}" beserta soal dan hasilnya akan dihapus permanen.`}
    confirmLabel="Ya, Hapus"
    onConfirm={confirmRemoveExam}
    close={() => (deletingExam = null)}
  />
{/if}
