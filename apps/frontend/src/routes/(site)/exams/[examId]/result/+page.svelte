<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Attempt, Answer, Exam, Question } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";
  import { statusLabel } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";

  let exam: Exam | null = null;
  let attempt: Attempt | null = null;
  let answers: Answer[] = [];
  let reviewQuestions: Question[] = [];
  let loading = true;
  let error = "";
  let grading = false;

  const QTYPE_BADGES: Record<string, string> = {
    essay: "Esai",
    multiple_choice: "Pilihan Ganda",
    true_false: "Benar/Salah",
    multi_select: "Pilih Banyak",
    numeric: "Angka",
    fill_blank: "Isian",
    matching: "Cocokkan",
    ordering: "Urutkan",
  };

  const examId = $page.params.examId;
  const attemptId = $page.url.searchParams.get("attempt") ?? "";

  async function load() {
    try {
      const res = await api.get<{
        attempt: Attempt;
        exam: Exam;
        answers: Answer[];
        questions: Question[];
      }>(`/attempts/${attemptId}/result`);
      attempt = res.attempt;
      exam = res.exam;
      answers = res.answers;
      // Graded attempts include the questions with the answer key for review.
      reviewQuestions = res.questions ?? [];
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat hasil";
    } finally {
      loading = false;
    }
  }

  async function gradeNow() {
    grading = true;
    try {
      await api.post("/ai/grade", { attempt_id: attemptId });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Penilaian gagal";
    } finally {
      grading = false;
    }
  }

  function questionFor(qid: string) {
    return (reviewQuestions.length ? reviewQuestions : (exam?.questions ?? [])).find(
      (q) => q.id === qid,
    );
  }

  onMount(load);
</script>

<svelte:head><title>Hasil Ujian — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  {#if loading}
    <p class="muted">Memuat hasil…</p>
  {:else if error}
    <p class="alert-error">
      {error}
    </p>
  {:else if attempt}
    <a href={`/exams/${examId}`} class="text-sm text-primary inline-flex items-center gap-1">
      <Icon name="arrow-left" size="11px" /> Kembali ke ujian
    </a>
    <div class="card mt-3">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p class="mono-label">Hasil Ujian</p>
          <h1 class="mt-1 font-display text-3xl font-bold">{exam?.title ?? "Hasil"}</h1>
          <p class="muted text-sm mt-0.5">
            Percobaan #{attempt.attempt_number} · Status: {statusLabel(attempt.status)}
          </p>
        </div>
        <div class="text-right">
          <div class="font-display text-4xl font-bold text-primary">
            {bpToPercent(attempt.score_bp)}
          </div>
          {#if attempt.passed !== null && attempt.passed !== undefined}
            <span
              class="badge mt-1"
              class:badge-mint={attempt.passed}
              class:badge-magenta={!attempt.passed}
            >
              <Icon name={attempt.passed ? "circle-check" : "circle-xmark"} size="11px" />
              {attempt.passed ? "Lulus" : "Tidak lulus"}
            </span>
          {/if}
        </div>
      </div>

      <!-- Quick summary metrics -->
      <div class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 border-t pt-4 text-xs">
        <div class="rounded-lg bg-surface-elevated/40 p-2.5">
          <span class="muted block">Total Soal</span>
          <span class="font-bold text-sm">{answers.length}</span>
        </div>
        <div class="rounded-lg bg-surface-elevated/40 p-2.5">
          <span class="muted block">Dijawab</span>
          <span class="font-bold text-sm"
            >{answers.filter((x) => x.answer_text && x.answer_text.trim()).length}</span
          >
        </div>
        <div class="rounded-lg bg-surface-elevated/40 p-2.5">
          <span class="muted block">Batas Kelulusan</span>
          <span class="font-bold text-sm"
            >{exam?.passing_score_bp ? bpToPercent(exam.passing_score_bp) : "—"}</span
          >
        </div>
        <div class="rounded-lg bg-surface-elevated/40 p-2.5">
          <span class="muted block">Status Kelulusan</span>
          <span class="font-bold text-sm {attempt.passed ? 'text-mint' : 'text-danger'}">
            {attempt.passed ? "Memenuhi syarat" : "Belum memenuhi"}
          </span>
        </div>
      </div>

      {#if attempt.status !== "graded" && (attempt.status === "submitted" || attempt.status === "grading_failed")}
        <button class="btn-primary mt-4" on:click={gradeNow} disabled={grading}>
          {grading ? "Menilai…" : "Nilai sekarang (AI)"}
        </button>
      {/if}
    </div>

    <div class="mt-4 space-y-4">
      {#each answers as a, i}
        {@const q = questionFor(a.question_id)}
        {@const currentScore = a.score_bp ?? 0}
        {@const isFullScore = a.max_score_bp > 0 && currentScore >= a.max_score_bp}
        {@const isZeroScore = a.score_bp !== null && a.score_bp !== undefined && currentScore === 0}
        <div class="card transition-all">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-2">
              <span class="font-bold text-sm mt-0.5 text-primary">#{i + 1}</span>
              <div>
                <div class="flex items-center gap-2 mb-1">
                  <span class="badge badge-indigo text-[10px]">
                    {QTYPE_BADGES[q?.qtype ?? ""] ?? q?.qtype ?? "Soal"}
                  </span>
                </div>
                <p class="font-medium text-sm leading-relaxed">{q?.prompt ?? "Soal"}</p>
              </div>
            </div>
            <div class="text-right shrink-0">
              <span
                class="badge"
                class:badge-mint={isFullScore}
                class:badge-amber={!isFullScore && !isZeroScore}
                class:badge-magenta={isZeroScore}
              >
                {bpToPercent(a.score_bp)} / {bpToPercent(a.max_score_bp, 0)}
              </span>
            </div>
          </div>
          {#if q?.qtype === "multiple_choice"}
            <ul class="mt-3 space-y-1 text-sm">
              {#each q.options ?? [] as opt}
                {@const chosen = (a.answer_text ?? "").toUpperCase() === opt.label}
                <li
                  class="flex items-center gap-2 rounded-sm border px-2 py-1"
                  class:border-secondary={opt.is_correct}
                  class:border-tertiary={chosen && !opt.is_correct}
                >
                  <span class="mono text-xs muted">{opt.label}.</span>
                  <span class="flex-1">{opt.text}</span>
                  {#if opt.is_correct}
                    <span class="badge badge-mint">Benar</span>
                  {/if}
                  {#if chosen}
                    <span class="badge badge-indigo">Pilihanmu</span>
                  {/if}
                </li>
              {/each}
            </ul>
            {#if !(q.options ?? []).some((o) => o.label === (a.answer_text ?? "").toUpperCase())}
              <p class="mt-2 text-xs muted">Kamu tidak menjawab soal ini.</p>
            {/if}
          {:else if q?.qtype === "true_false"}
            {@const studentAns = (a.answer_text ?? "").toLowerCase()}
            {@const correctAns = (q.correct_answer ?? "").toLowerCase()}
            <div class="mt-3 flex items-center gap-3 text-sm">
              <span class="muted text-xs">Jawabanmu:</span>
              <span
                class="badge"
                class:badge-mint={studentAns === correctAns}
                class:badge-magenta={studentAns !== correctAns}
              >
                {studentAns === "true"
                  ? "Benar"
                  : studentAns === "false"
                    ? "Salah"
                    : studentAns || "(kosong)"}
              </span>
              {#if studentAns !== correctAns && correctAns}
                <span class="muted text-xs">Kunci:</span>
                <span class="badge badge-mint">{correctAns === "true" ? "Benar" : "Salah"}</span>
              {/if}
            </div>
          {:else}
            <p class="mt-3 whitespace-pre-wrap text-sm">{a.answer_text ?? "(tanpa jawaban)"}</p>
          {/if}
          {#if a.feedback}
            <div class="alert-info mt-3">
              <span>
                <strong>Umpan balik:</strong>
                {a.feedback}
                {#if a.similarity_bp !== null && a.similarity_bp !== undefined}
                  <span class="muted"> · kemiripan {bpToPercent(a.similarity_bp)}</span>
                {/if}
              </span>
            </div>
          {/if}
          {#if q?.qtype !== "multiple_choice" && q?.correct_answer}
            <details class="mt-3 text-sm">
              <summary class="cursor-pointer muted">Tampilkan jawaban acuan</summary>
              <p class="mt-2">{q.correct_answer}</p>
            </details>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
