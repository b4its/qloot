<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import { paginate } from "$lib/utils/format";
  import { reveal } from "$lib/actions/reveal";
  import { formatDate, examCategory, type ExamCategory } from "$lib/utils/format";

  const PAGE_SIZE = 10;

  /** Filter tabs: all exams, or one of the two categories (multiple-choice /
   * essay). "mixed" exams (both question kinds) only appear under "Semua". */
  type Filter = "all" | "multiple_choice" | "essay" | "mixed";

  let exams: Exam[] = [];
  let loading = true;
  let error = "";
  let currentPage = 1;
  let filter: Filter = "all";

  $: canManage = hasRole($auth.user, "teacher");

  // Bucket every exam by category once, so the tabs and the rendered list stay
  // consistent and we never reclassify inside the template.
  $: categorized = exams.map((exam) => ({ exam, category: examCategory(exam) }));
  $: counts = {
    all: categorized.length,
    multiple_choice: categorized.filter((e) => e.category === "multiple_choice").length,
    essay: categorized.filter((e) => e.category === "essay").length,
    mixed: categorized.filter((e) => e.category === "mixed").length,
  };
  $: filtered = (
    filter === "all" ? categorized : categorized.filter((e) => e.category === filter)
  ).map((e) => e.exam);

  $: totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedExams = paginate(filtered, currentPage, PAGE_SIZE);

  /** Section headings for the "Semua" view: PG first, then Esai, then campuran. */
  const SECTIONS: { key: ExamCategory; label: string }[] = [
    { key: "multiple_choice", label: "Pilihan Ganda" },
    { key: "essay", label: "Esai" },
    { key: "mixed", label: "Campuran" },
  ];

  function selectFilter(f: Filter) {
    filter = f;
    currentPage = 1;
  }

  function categoryOf(exam: Exam): ExamCategory {
    return examCategory(exam);
  }

  function badgeLabel(category: ExamCategory): string {
    return category === "multiple_choice"
      ? "PG"
      : category === "essay"
        ? "Esai"
        : category === "mixed"
          ? "Campuran"
          : "—";
  }

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
      <p class="mt-2 muted">
        Ujian dibagi menjadi <strong>pilihan ganda</strong> (dinilai otomatis) dan
        <strong>esai</strong> (dinilai AI).
      </p>
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

    {#if filtered.length === 0}
      <div class="card mt-6 grid place-items-center py-16 text-center">
        <Icon name="file-pen" size="28px" class="muted" />
        <p class="mt-3 font-semibold">Tidak ada ujian di kategori ini</p>
        <p class="text-sm muted">Pilih kategori lain untuk melihat ujian yang tersedia.</p>
      </div>
    {:else if filter === "all"}
      {#each SECTIONS as section}
        {@const sectionExams = pagedExams.filter((e) => categoryOf(e) === section.key)}
        {#if sectionExams.length}
          <section class="mt-8">
            <h2 class="hud flex items-center gap-2 font-display text-xl font-bold">
              {section.label}
              <span class="badge badge-indigo">{sectionExams.length}</span>
            </h2>
            <div class="mt-4 grid gap-5 sm:grid-cols-2">
              {#each sectionExams as exam, i}
                <a
                  href={`/exams/${exam.id}`}
                  use:reveal={{ delay: i * 40 }}
                  class="card lift block"
                >
                  <div class="flex items-center justify-between">
                    <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
                      <Icon name="file-pen" size="17px" />
                    </span>
                    <span class="flex items-center gap-2">
                      <span
                        class="badge"
                        class:badge-indigo={section.key === "multiple_choice"}
                        class:badge-magenta={section.key === "essay"}
                        class:badge-neutral={section.key === "mixed"}
                      >
                        {badgeLabel(section.key)}
                      </span>
                      <span
                        class="badge"
                        class:badge-mint={exam.is_active}
                        class:badge-neutral={!exam.is_active}
                      >
                        <Icon name={exam.is_active ? "lock-open" : "lock"} size="9px" />
                        {exam.is_active ? "terbuka" : exam.status}
                      </span>
                    </span>
                  </div>
                  <h3 class="mt-3 font-display text-lg font-bold">{exam.title}</h3>
                  <div class="mono-label mt-2 flex flex-wrap items-center gap-3">
                    <span><Icon name="clock" size="10px" /> {exam.duration_minutes} menit</span>
                    <span>·</span>
                    <span
                      ><Icon name="bullseye" size="10px" /> lulus {(
                        exam.passing_score_bp / 100
                      ).toFixed(0)}%</span
                    >
                    {#if exam.question_count}
                      <span>·</span>
                      <span>{exam.question_count} soal</span>
                    {/if}
                  </div>
                  {#if exam.opens_at}<p class="mt-2 text-xs muted">
                      Mulai {formatDate(exam.opens_at)}
                    </p>{/if}
                </a>
              {/each}
            </div>
          </section>
        {/if}
      {/each}
    {:else}
      <div class="mt-6 grid gap-5 sm:grid-cols-2">
        {#each pagedExams as exam, i}
          <a href={`/exams/${exam.id}`} use:reveal={{ delay: i * 40 }} class="card lift block">
            <div class="flex items-center justify-between">
              <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
                <Icon name="file-pen" size="17px" />
              </span>
              <span class="flex items-center gap-2">
                <span
                  class="badge"
                  class:badge-indigo={filter === "multiple_choice"}
                  class:badge-magenta={filter === "essay"}
                  class:badge-neutral={filter === "mixed"}
                >
                  {badgeLabel(categoryOf(exam))}
                </span>
                <span
                  class="badge"
                  class:badge-mint={exam.is_active}
                  class:badge-neutral={!exam.is_active}
                >
                  <Icon name={exam.is_active ? "lock-open" : "lock"} size="9px" />
                  {exam.is_active ? "terbuka" : exam.status}
                </span>
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
              {#if exam.question_count}
                <span>·</span>
                <span>{exam.question_count} soal</span>
              {/if}
            </div>
            {#if exam.opens_at}<p class="mt-2 text-xs muted">
                Mulai {formatDate(exam.opens_at)}
              </p>{/if}
          </a>
        {/each}
      </div>
    {/if}

    <Pagination
      page={currentPage}
      pageSize={PAGE_SIZE}
      total={filtered.length}
      {loading}
      label="ujian"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>
