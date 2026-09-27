<script lang="ts">
  import { onMount } from "svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Attempt } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { bpToPercent, examCategory, statusLabel, paginate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";

  const PAGE_SIZE = 10;
  let exam: Exam | null = null;
  let loading = true;
  let loadError = "";
  let actionError = "";
  let starting = false;
  let managing = "";
  let pastAttempts: Attempt[] = [];
  let attemptPage = 1;

  const examId = $page.params.examId;
  $: canManage = hasRole($auth.user, "teacher");

  // --- attempt-derived state -------------------------------------------------
  $: scored = pastAttempts.filter((a) => a.score_bp !== null && a.score_bp !== undefined);
  $: bestScoreBp = scored.length ? Math.max(...scored.map((a) => a.score_bp ?? 0)) : null;
  $: bestPassed = bestScoreBp !== null && exam ? bestScoreBp >= exam.passing_score_bp : null;
  $: inProgress = pastAttempts.find((a) => a.status === "in_progress") ?? null;
  $: passedAny = pastAttempts.some((a) => a.passed === true);
  // Remaining attempts for the caller (null when unlimited or unknown).
  $: remainingAttempts =
    exam?.max_attempts && exam.max_attempts > 0
      ? Math.max(0, exam.max_attempts - pastAttempts.length)
      : null;
  $: category = exam ? examCategory(exam) : "empty";
  $: categoryLabel =
    category === "multiple_choice"
      ? "Pilihan Ganda"
      : category === "essay"
        ? "Esai"
        : category === "mixed"
          ? "Campuran"
          : "Belum ada soal";
  $: totalPages = Math.max(1, Math.ceil(pastAttempts.length / PAGE_SIZE));
  $: if (attemptPage > totalPages) attemptPage = 1;
  $: pagedAttempts = paginate(pastAttempts, attemptPage, PAGE_SIZE);
  $: now = Date.now();
  $: opensAt = exam?.opens_at ? new Date(exam.opens_at).getTime() : null;
  $: closesAt = exam?.closes_at ? new Date(exam.closes_at).getTime() : null;
  $: availability = !exam?.is_active
    ? "closed"
    : opensAt !== null && now < opensAt
      ? "upcoming"
      : closesAt !== null && now > closesAt
        ? "closed"
        : "open";

  async function load() {
    try {
      exam = await api.get<Exam>(`/exams/${examId}`);
      pastAttempts = await api.get<Attempt[]>(`/attempts?exam_id=${examId}&limit=200`);
    } catch (e) {
      loadError = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    } finally {
      loading = false;
    }
  }

  async function manage(action: "publish" | "close") {
    actionError = "";
    managing = action;
    try {
      await api.post(`/exams/${examId}/${action}`);
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : "Gagal mengubah status ujian";
    } finally {
      managing = "";
    }
  }

  async function start() {
    actionError = "";
    starting = true;
    try {
      const attempt = await api.post<Attempt>(`/exams/${examId}/attempts`);
      await goto(`/exams/${examId}/attempt?attempt=${attempt.id}`);
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : "Gagal memulai pengerjaan";
    } finally {
      starting = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>{exam?.title ?? "Ujian"} — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  {#if loading}
    <Skeleton rows={4} />
  {:else if loadError}
    <p class="alert-error" role="alert" aria-live="assertive">
      {loadError}
    </p>
  {:else if exam}
    <a href="/exams" class="text-sm text-primary">← Semua ujian</a>
    <p class="mono-label mt-4">Ujian</p>
    <h1 class="mt-2 font-display text-3xl font-bold">{exam.title}</h1>
    <div class="mt-2 flex flex-wrap items-center gap-2">
      <span
        class="badge"
        class:badge-indigo={category === "multiple_choice"}
        class:badge-magenta={category === "essay"}
        class:badge-neutral={category === "mixed" || category === "empty"}>{categoryLabel}</span
      >
      <span class="badge badge-neutral"
        ><Icon name="clock" size="9px" /> {exam.duration_minutes} menit</span
      >
      <span class="badge badge-neutral"
        ><Icon name="bullseye" size="9px" /> lulus {(exam.passing_score_bp / 100).toFixed(0)}%</span
      >
      <span class="badge badge-neutral"
        >{exam.question_count ?? exam.questions?.length ?? 0} soal</span
      >
      {#if passedAny}<span class="badge badge-mint"
          ><Icon name="circle-check" size="9px" /> Sudah lulus</span
        >{/if}
    </div>

    {#if canManage}
      <div class="mt-4 flex gap-2">
        <button
          class="btn-primary"
          on:click={() => manage("publish")}
          disabled={managing === "publish"}
        >
          {managing === "publish" ? "…" : "Terbitkan"}</button
        >
        <button class="btn-ghost" on:click={() => manage("close")} disabled={managing === "close"}>
          {managing === "close" ? "…" : "Tutup"}</button
        >
        <a href="/teacher/exams" class="btn-ghost">Sunting di Guru</a>
      </div>
    {/if}

    {#if actionError}
      <p class="alert-error mt-4" role="alert">{actionError}</p>
    {/if}

    {#if exam.instructions}
      <section class="card mt-6" aria-labelledby="exam-instructions-title">
        <h2 id="exam-instructions-title" class="hud font-display text-lg font-bold">
          Instruksi pengerjaan
        </h2>
        <p class="mt-2 whitespace-pre-wrap text-sm leading-relaxed muted">{exam.instructions}</p>
      </section>
    {/if}

    <!-- Score metrics -->
    {#if !canManage && (bestScoreBp !== null || pastAttempts.length > 0)}
      <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="card p-4">
          <p class="mono-label text-[10px]">Skor terbaik</p>
          <p
            class="mt-1 font-display text-2xl font-bold"
            class:text-mint={bestPassed}
            class:text-highlight={bestPassed === false}
            data-role="best-score"
          >
            {bestScoreBp !== null ? bpToPercent(bestScoreBp) : "—"}
          </p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Percobaan</p>
          <p class="mt-1 font-display text-2xl font-bold">{pastAttempts.length}</p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Sisa percobaan</p>
          <p class="mt-1 font-display text-2xl font-bold">
            {remainingAttempts === null ? "∞" : remainingAttempts}
          </p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Status</p>
          <p class="mt-1 font-display text-2xl font-bold">
            {passedAny ? "Lulus" : pastAttempts.length ? "Belum lulus" : "—"}
          </p>
        </div>
      </div>
    {/if}

    <!-- Resume an in-progress attempt -->
    {#if inProgress}
      <div class="card mt-4 border-amber-500/40">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2 text-amber-400">
            <Icon name="hourglass-half" size="15px" />
            <span class="text-sm font-medium">Ada pengerjaan yang belum diselesaikan.</span>
          </div>
          <a
            href={`/exams/${examId}/attempt?attempt=${inProgress.id}`}
            class="btn-primary !py-1.5 text-xs">Lanjutkan pengerjaan →</a
          >
        </div>
      </div>
    {/if}

    {#if availability === "open"}
      <div class="card mt-6">
        <h2 class="hud font-display text-lg font-bold">Siap mengerjakan ujian ini?</h2>
        <p class="mt-1 text-sm muted">
          Timer dikendalikan server. Jawabanmu tersimpan otomatis saat kamu mengerjakan.
        </p>
        {#if remainingAttempts !== null}
          <p class="mt-2 text-xs muted">
            {remainingAttempts > 0
              ? `Sisa percobaan: ${remainingAttempts}`
              : "Kamu telah menggunakan semua percobaan. Hubungi pengajar untuk percobaan tambahan."}
          </p>
        {/if}
        <button
          class="btn-primary mt-4"
          on:click={start}
          disabled={starting || remainingAttempts === 0 || !!inProgress}
          aria-describedby={exam.instructions ? "exam-instructions-title" : undefined}
        >
          {starting ? "Memulai…" : "Mulai mengerjakan"}
        </button>
      </div>
    {:else if availability === "upcoming"}
      <div class="card mt-6 border-amber/40">
        <p class="font-semibold text-amber">Ujian belum dibuka</p>
        <p class="mt-1 text-sm muted">
          Pengerjaan dapat dimulai pada {exam.opens_at
            ? new Date(exam.opens_at).toLocaleString("id-ID")
            : "jadwal yang ditentukan"}.
        </p>
      </div>
    {:else}
      <div class="card mt-6 muted">
        <p class="font-semibold text-foreground">Ujian sedang ditutup</p>
        {#if exam.closes_at}
          <p class="mt-1 text-sm">
            Batas pengerjaan: {new Date(exam.closes_at).toLocaleString("id-ID")}.
          </p>
        {/if}
      </div>
    {/if}

    {#if pastAttempts.length}
      <div class="card mt-4">
        <h2 class="hud font-display text-lg font-bold">Pengerjaanmu</h2>
        <ul class="mt-2 space-y-2 text-sm">
          {#each pagedAttempts as a (a.id)}
            {@const pct = a.score_bp !== null && a.score_bp !== undefined ? a.score_bp / 100 : null}
            <li class="flex items-center justify-between border-b pb-2 last:border-0">
              <span class="flex items-center gap-2">
                <span>Percobaan #{a.attempt_number}</span>
                <span
                  class="badge"
                  class:badge-mint={a.passed === true}
                  class:badge-magenta={a.passed === false}
                  class:badge-amber={a.status === "in_progress"}
                  class:badge-neutral={a.status !== "in_progress" && a.passed == null}
                >
                  {a.status === "in_progress" ? "Berjalan" : statusLabel(a.status)}
                </span>
              </span>
              <span class="flex items-center gap-2">
                {#if pct !== null}
                  <span
                    class="font-mono"
                    class:text-mint={a.passed === true}
                    class:text-tertiary={a.passed === false}
                  >
                    {pct.toFixed(1)}%
                  </span>
                {/if}
                <a href={`/exams/${examId}/result?attempt=${a.id}`} class="text-primary">Lihat</a>
              </span>
            </li>
          {/each}
        </ul>
        <Pagination
          page={attemptPage}
          pageSize={PAGE_SIZE}
          total={pastAttempts.length}
          label="pengerjaan"
          onPrev={() => (attemptPage = Math.max(1, attemptPage - 1))}
          onNext={() => (attemptPage = Math.min(totalPages, attemptPage + 1))}
        />
      </div>
    {/if}
  {/if}
</div>
