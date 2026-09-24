<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { ExamResultsReview, ExamResultReviewRow, ReviewAnswer } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import { bpToPercent, statusLabel } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const examId = $page.params.id;
  const PAGE = 25;

  let review: ExamResultsReview | null = null;
  let loading = true;
  let error = "";
  let currentPage = 1;
  let hasMore = false;
  // Which student's answer sheet is expanded (attempt id).
  let openAttempt: string | null = null;

  $: exam = review?.exam ?? null;
  $: results = review?.results ?? [];

  async function load() {
    loading = true;
    error = "";
    try {
      review = await api.get<ExamResultsReview>(
        `/exams/${examId}/results/review?limit=${PAGE}&offset=${(currentPage - 1) * PAGE}`,
      );
      hasMore = review.results.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat hasil";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = currentPage + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    currentPage = next;
    openAttempt = null;
    load();
  }

  function toggle(a: ExamResultReviewRow) {
    openAttempt = openAttempt === a.id ? null : a.id;
  }

  function correctnessLabel(v: boolean | null | undefined): string {
    return v === true ? "Benar" : v === false ? "Salah" : "—";
  }

  // --- regrade + per-answer override ---
  let busy = "";
  let message = "";
  // Per-answer draft overrides keyed by `${attemptId}:${questionId}`.
  let overrides: Record<string, { score: number; feedback: string }> = {};
  function draftFor(attemptId: string, ans: ReviewAnswer) {
    const k = `${attemptId}:${ans.question_id}`;
    if (!overrides[k]) {
      overrides[k] = {
        score: Math.round((ans.score_bp ?? 0) / 100),
        feedback: ans.feedback ?? "",
      };
    }
    return overrides[k];
  }

  async function regrade(attemptId: string) {
    busy = attemptId;
    error = "";
    try {
      await api.post(`/attempts/${attemptId}/regrade`);
      message = "Penilaian ulang diantrekan.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menilai ulang";
    } finally {
      busy = "";
    }
  }

  async function overrideAnswer(attemptId: string, ans: ReviewAnswer) {
    const draft = draftFor(attemptId, ans);
    busy = `${attemptId}:${ans.question_id}`;
    error = "";
    try {
      // The input is a percent (0-100); convert to basis points.
      await api.post(
        `/attempts/${attemptId}/answers/${ans.question_id}/override`,
        {
          score_bp: Math.max(0, Math.min(10000, Math.round(draft.score * 100))),
          feedback: draft.feedback || null,
        },
      );
      message = "Nilai jawaban diperbarui.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyimpan nilai";
    } finally {
      busy = "";
    }
  }

  interface PlagiarismFinding {
    prompt: string;
    a_name: string;
    b_name: string;
    similarity_bp: number;
  }
  let plagiarism: PlagiarismFinding[] = [];
  let plagiarismChecked = false;

  async function loadPlagiarism() {
    try {
      const res = await api.get<{ findings: PlagiarismFinding[] }>(`/exams/${examId}/plagiarism`);
      plagiarism = res?.findings ?? [];
    } catch {
      plagiarism = [];
    } finally {
      plagiarismChecked = true;
    }
  }

  onMount(load);
  onMount(loadPlagiarism);
</script>

<svelte:head><title>Hasil Ujian — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Ujian"
    title="Hasil peserta"
    subtitle={exam?.title ?? "Hasil ujian"}
    backHref={`/teacher/exams/${examId}`}
    backLabel="Kelola ujian"
  />

  <PageAlerts {error} {message} />

  {#if plagiarismChecked && plagiarism.length}
    <div class="card mt-4 border-tertiary">
      <p class="mono-label mb-2 text-tertiary">
        <Icon name="clone" size="11px" /> Indikasi kemiripan jawaban esai
      </p>
      <ul class="space-y-1 text-sm">
        {#each plagiarism.slice(0, 10) as f}
          <li class="flex flex-wrap items-center justify-between gap-2 border-b pb-1 last:border-0">
            <span class="truncate">{f.a_name} ↔ {f.b_name}</span>
            <span class="mono text-xs text-tertiary">{bpToPercent(f.similarity_bp)}</span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if loading}
    <div class="mt-6 space-y-2">
      {#each Array(4) as _}<div class="skeleton h-10"></div>{/each}
    </div>
  {:else if results.length === 0}
    <div class="card mt-6 grid place-items-center py-12 text-center">
      <Icon name="inbox" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada pengumpulan</p>
      <p class="text-sm muted">Hasil akan muncul setelah siswa mengerjakan ujian.</p>
    </div>
  {:else}
    <p class="mt-4 text-xs muted">
      Klik seorang peserta untuk melihat soal, jawaban, dan benarnya.
    </p>
    <div class="mt-3 space-y-2">
      {#each results as a (a.id)}
        <div class="card !p-0">
          <button
            type="button"
            class="flex w-full flex-wrap items-center justify-between gap-3 px-5 py-3 text-left"
            on:click={() => toggle(a)}
            aria-expanded={openAttempt === a.id}
          >
            <span class="flex items-center gap-2">
              <Icon
                name={openAttempt === a.id ? "chevron-down" : "chevron-right"}
                size="11px"
                class="muted"
              />
              <span class="font-semibold">
                {a.display_name ?? `${a.user_id.slice(0, 8)}…`}
              </span>
              <span class="text-xs muted">Percobaan #{a.attempt_number}</span>
            </span>
            <span class="flex items-center gap-3">
              <span
                class="badge"
                class:badge-mint={a.passed === true}
                class:badge-magenta={a.passed === false}
                class:badge-neutral={a.passed === null || a.passed === undefined}
              >
                {statusLabel(a.status)}
              </span>
              <span class="font-mono text-sm">
                {a.score_bp !== null && a.score_bp !== undefined ? bpToPercent(a.score_bp) : "—"}
              </span>
              {#if a.is_flagged}
                <span class="badge badge-magenta" title={a.flag_reason ?? ""}>
                  <Icon name="triangle-exclamation" size="10px" /> Terindikasi
                </span>
              {/if}
            </span>
          </button>

          {#if openAttempt === a.id}
            <div class="border-t px-5 py-4">
              {#if a.status === "submitted" || a.status === "grading_failed"}
                <button
                  class="btn-ghost mb-3 !py-1 text-xs"
                  on:click={() => regrade(a.id)}
                  disabled={busy === a.id}>{busy === a.id ? "…" : "Nilai ulang"}</button
                >
              {/if}
              {#if a.answers.length === 0}
                <p class="text-sm muted">Peserta ini tidak menjawab soal apa pun.</p>
              {:else}
                <ol class="space-y-3 text-sm">
                  {#each a.answers as ans}
                    <li class="border-b pb-3 last:border-0 last:pb-0">
                      <div class="flex items-start justify-between gap-3">
                        <p class="font-medium">
                          <span class="mono-label mr-1"
                            >{ans.qtype === "multiple_choice" ? "PG" : "Esai"}</span
                          >
                          {ans.prompt}
                        </p>
                        <span class="flex flex-none items-center gap-2">
                          {#if ans.qtype === "multiple_choice"}
                            <span
                              class="badge"
                              class:badge-mint={ans.is_correct === true}
                              class:badge-magenta={ans.is_correct === false}
                              class:badge-neutral={ans.is_correct === null ||
                                ans.is_correct === undefined}
                            >
                              {correctnessLabel(ans.is_correct)}
                            </span>
                          {/if}
                          <span class="mono text-xs muted">
                            {bpToPercent(ans.score_bp)} / {bpToPercent(ans.max_score_bp, 0)}
                          </span>
                        </span>
                      </div>
                      <p class="mt-1 text-ink2">
                        <span class="mono-label">Jawaban:</span>
                        {#if ans.qtype === "multiple_choice"}
                          {#if ans.answer_text}
                            <span class="mono">{ans.answer_text}.</span>
                            {ans.answer_display ?? "(opsi tidak dikenal)"}
                          {:else}
                            <span class="muted">tidak dijawab</span>
                          {/if}
                        {:else}
                          {ans.answer_text ?? "(tanpa jawaban)"}
                        {/if}
                      </p>
                      {#if ans.qtype === "multiple_choice" && ans.is_correct === false && ans.correct_answer}
                        <p class="mt-0.5 text-xs text-tertiary">
                          Kunci: <span class="mono">{ans.correct_answer}.</span>
                          {ans.correct_display ?? ""}
                        </p>
                      {/if}
                      {#if ans.feedback && ans.qtype !== "multiple_choice"}
                        <p class="mt-1 text-xs muted">Umpan balik: {ans.feedback}</p>
                      {/if}
                      {#if ans.similarity_bp !== null && ans.similarity_bp !== undefined}
                        <p class="mt-0.5 text-xs muted">
                          Kemiripan dengan acuan: {bpToPercent(ans.similarity_bp)}
                        </p>
                      {/if}
                      {#if a.status === "graded" || a.status === "submitted"}
                        {@const d = draftFor(a.id, ans)}
                        <div class="mt-2 flex flex-wrap items-center gap-2">
                          <span class="mono-label">Override nilai (%)</span>
                          <input
                            class="input !w-20 !py-1 text-sm"
                            type="number"
                            min="0"
                            max="100"
                            bind:value={d.score}
                          />
                          <input
                            class="input !py-1 text-sm"
                            placeholder="Umpan balik"
                            bind:value={d.feedback}
                          />
                          <button
                            class="btn-secondary !py-1 text-xs"
                            on:click={() => overrideAnswer(a.id, ans)}
                            disabled={busy === `${a.id}:${ans.question_id}`}
                            >{busy === `${a.id}:${ans.question_id}` ? "…" : "Simpan"}</button
                          >
                        </div>
                      {/if}
                    </li>
                  {/each}
                </ol>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
    <Pagination
      page={currentPage}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="peserta"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {/if}
</div>
