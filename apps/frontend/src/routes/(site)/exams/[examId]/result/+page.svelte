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
  let actionError = "";
  let grading = false;
  // Review filter: focus on questions by result category.
  type ScoreFilter = "all" | "correct" | "partial" | "wrong" | "unanswered" | "pending";
  let scoreFilter: ScoreFilter = "all";

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
    actionError = "";
    try {
      await api.post("/ai/grade", { attempt_id: attemptId });
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : "Penilaian gagal";
    } finally {
      grading = false;
    }
  }

  function questionFor(qid: string) {
    return (reviewQuestions.length ? reviewQuestions : (exam?.questions ?? [])).find(
      (q) => q.id === qid,
    );
  }

  // --- per-question result classification ------------------------------------
  type Bucket = "correct" | "partial" | "wrong" | "unanswered" | "pending";
  // An answered essay that the AI has not scored yet (score_bp === null) is
  // "pending", not "wrong" — otherwise ungraded work is mislabeled as incorrect.
  function bucketOf(a: Answer): Bucket {
    const answered = !!(a.answer_text && a.answer_text.trim());
    if (!answered) return "unanswered";
    if (a.score_bp === null || a.score_bp === undefined) return "pending";
    const score = a.score_bp;
    if (a.max_score_bp > 0 && score >= a.max_score_bp) return "correct";
    if (score > 0) return "partial";
    return "wrong";
  }

  $: buckets = answers.map((a) => bucketOf(a));
  $: counts = {
    correct: buckets.filter((b) => b === "correct").length,
    partial: buckets.filter((b) => b === "partial").length,
    wrong: buckets.filter((b) => b === "wrong").length,
    unanswered: buckets.filter((b) => b === "unanswered").length,
    pending: buckets.filter((b) => b === "pending").length,
  };
  // Keep the original question number when filtering, so the #N stays stable.
  $: indexedAnswers = answers.map((a, i) => ({ a, i, bucket: buckets[i] }));
  $: filteredAnswers = indexedAnswers.filter(
    (x) => scoreFilter === "all" || x.bucket === scoreFilter,
  );

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
      {#if actionError}
        <p class="alert-error mt-3" role="alert" aria-live="assertive">
          <Icon name="triangle-exclamation" size="12px" class="mt-0.5 flex-none" />
          {actionError}
        </p>
      {/if}
    </div>

    <!-- Review filter -->
    <div
      class="mt-6 flex flex-wrap items-center gap-1"
      role="tablist"
      aria-label="Filter hasil soal"
    >
      {#each [["all", `Semua (${answers.length})`], ["correct", `Benar (${counts.correct})`], ["partial", `Sebagian (${counts.partial})`], ["wrong", `Salah (${counts.wrong})`], ["pending", `Menunggu nilai (${counts.pending})`], ["unanswered", `Kosong (${counts.unanswered})`]] as [val, label]}
        <button
          type="button"
          role="tab"
          aria-selected={scoreFilter === val}
          class="btn-ghost !py-1 text-xs"
          class:bg-primary={scoreFilter === val}
          class:!text-white={scoreFilter === val}
          on:click={() => (scoreFilter = val as ScoreFilter)}
        >
          {label}
        </button>
      {/each}
    </div>

    <div class="mt-4 space-y-4">
      {#if filteredAnswers.length === 0}
        <div class="card text-center py-8">
          <p class="muted text-sm">Tidak ada soal pada kategori ini.</p>
        </div>
      {/if}
      {#each filteredAnswers as { a, i }}
        {@const q = questionFor(a.question_id)}
        {@const currentScore = a.score_bp ?? 0}
        {@const isFullScore = a.max_score_bp > 0 && currentScore >= a.max_score_bp}
        {@const isZeroScore = a.score_bp !== null && a.score_bp !== undefined && currentScore === 0}
        {@const isPending = a.score_bp === null || a.score_bp === undefined}
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
                {#if q}
                  <p class="font-medium text-sm leading-relaxed">{q.prompt}</p>
                {:else}
                  <p class="text-sm muted italic">
                    Detail soal tidak tersedia untuk ditinjau, namun jawabanmu tetap tersimpan.
                  </p>
                {/if}
              </div>
            </div>
            <div class="text-right shrink-0">
              {#if isPending}
                <span class="badge badge-amber">
                  <Icon name="hourglass-half" size="10px" /> Menunggu nilai
                </span>
              {:else}
                <span
                  class="badge"
                  class:badge-mint={isFullScore}
                  class:badge-amber={!isFullScore && !isZeroScore}
                  class:badge-magenta={isZeroScore}
                >
                  {bpToPercent(a.score_bp)} / {bpToPercent(a.max_score_bp, 0)}
                </span>
              {/if}
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
