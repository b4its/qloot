<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import Dialog from "$lib/components/Dialog.svelte";
  import { onMount, onDestroy, tick } from "svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Attempt, Answer } from "$lib/types";

  let exam: Exam | null = null;
  let attempt: Attempt | null = null;
  // Attempt-scoped, deterministically shuffled questions/options.
  let questions: NonNullable<Exam["questions"]> = [];
  let answers: Record<string, string> = {};
  let saved: Record<string, "idle" | "saving" | "saved" | "error"> = {};
  let flagged: Record<string, boolean> = {};
  let showSubmitModal = false;
  let loading = true;
  let error = "";
  let current = 0;
  let secondsLeft = 0;
  let ticker: ReturnType<typeof setInterval> | null = null;
  let submitting = false;
  let submitError = "";
  let loadWarning = "";
  let finished = false;
  const autosaveTimers: Record<string, ReturnType<typeof setTimeout>> = {};
  const revisions: Record<string, number> = {};
  const saveChains: Record<string, Promise<void>> = {};

  const QTYPE_LABELS: Record<string, string> = {
    multiple_choice: "Pilihan Ganda",
    true_false: "Benar / Salah",
    multi_select: "Pilihan Jamak",
    numeric: "Jawaban Angka",
    fill_blank: "Isian Singkat",
    ordering: "Urutan Item",
    matching: "Pencocokan Pasangan",
    essay: "Esai",
  };

  const examId = $page.params.examId;
  const attemptId = $page.url.searchParams.get("attempt") ?? "";

  function toggleFlag(qid: string) {
    flagged[qid] = !flagged[qid];
    flagged = { ...flagged };
  }

  function isAnswered(qid: string, currentAnswers: Record<string, string>): boolean {
    const raw = currentAnswers[qid];
    if (raw === undefined || raw === null || raw === "") return false;
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed.length > 0;
      if (typeof parsed === "object" && parsed !== null) return Object.keys(parsed).length > 0;
    } catch {
      // plain text string
    }
    return String(raw).trim().length > 0;
  }

  $: answeredCount = questions.filter((q) => isAnswered(q.id, answers)).length;
  $: flaggedCount = questions.filter((q) => flagged[q.id]).length;
  $: unansweredCount = Math.max(0, questions.length - answeredCount);
  $: progressPercent =
    questions.length > 0 ? Math.round((answeredCount / questions.length) * 100) : 0;
  $: failedCount = questions.filter((q) => saved[q.id] === "error").length;
  $: savingCount = questions.filter((q) => saved[q.id] === "saving").length;

  function warnBeforeUnload(e: BeforeUnloadEvent) {
    if (finished || secondsLeft <= 0) return;
    e.preventDefault();
    e.returnValue = "";
  }

  async function load() {
    if (!attemptId) {
      error = "ID pengerjaan tidak ditemukan. Mulai atau lanjutkan ujian dari halaman detail.";
      loading = false;
      return;
    }
    try {
      [exam, attempt] = await Promise.all([
        api.get<Exam>(`/exams/${examId}`),
        api.get<Attempt>(`/attempts/${attemptId}`),
      ]);
      if (attempt.exam_id !== examId) throw new Error("Pengerjaan tidak cocok dengan ujian ini");
      if (attempt.status !== "in_progress") {
        finished = true;
        await goto(`/exams/${examId}/result?attempt=${attemptId}`);
        return;
      }
      questions = await api.get<NonNullable<Exam["questions"]>>(`/attempts/${attemptId}/questions`);
      try {
        const res = await api.get<{ answers: Answer[] }>(`/attempts/${attemptId}/result`);
        for (const a of res.answers) {
          if (a.answer_text) {
            answers[a.question_id] = a.answer_text;
            saved[a.question_id] = "saved";
          }
        }
      } catch {
        loadWarning =
          "Jawaban tersimpan sebelumnya belum dapat dimuat. Muat ulang sebelum melanjutkan.";
      }
      answers = { ...answers };
      saved = { ...saved };
      startTimer();
    } catch (e) {
      error =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Gagal memuat ujian";
    } finally {
      loading = false;
    }
  }

  function startTimer() {
    if (!exam || !attempt) return;
    // Prefer the server-authoritative expiry; fall back to started_at+duration.
    const deadline = attempt.expires_at
      ? new Date(attempt.expires_at).getTime()
      : new Date(attempt.started_at).getTime() + exam.duration_minutes * 60_000;
    const update = () => {
      secondsLeft = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      if (secondsLeft === 0) {
        if (ticker) clearInterval(ticker);
        executeSubmit();
      }
    };
    update();
    ticker = setInterval(update, 1000);
  }

  function multiSelections(qid: string): string[] {
    try {
      const raw = JSON.parse(answers[qid] ?? "[]");
      return Array.isArray(raw) ? raw.map((x) => String(x)) : [];
    } catch {
      return [];
    }
  }

  function orderingText(qid: string): string {
    try {
      const raw = JSON.parse(answers[qid] ?? "[]");
      return Array.isArray(raw) ? raw.join("\n") : "";
    } catch {
      return "";
    }
  }

  function matchingText(qid: string): string {
    try {
      const raw = JSON.parse(answers[qid] ?? "{}");
      if (raw && typeof raw === "object")
        return Object.entries(raw)
          .map(([k, v]) => `${k}=${v}`)
          .join("\n");
      return "";
    } catch {
      return "";
    }
  }

  function onInput(qid: string) {
    answers = { ...answers };
    revisions[qid] = (revisions[qid] ?? 0) + 1;
    saved[qid] = "idle";
    saved = { ...saved };
    if (autosaveTimers[qid]) clearTimeout(autosaveTimers[qid]);
    autosaveTimers[qid] = setTimeout(() => {
      delete autosaveTimers[qid];
      void saveAnswer(qid);
    }, 800);
  }

  function isTransient(error: unknown): boolean {
    return !(error instanceof ApiError) || [408, 429, 502, 503, 504].includes(error.status);
  }

  function saveAnswer(qid: string, required = false): Promise<void> {
    const revision = revisions[qid] ?? 0;
    const value = answers[qid] ?? "";
    const previous = saveChains[qid] ?? Promise.resolve();
    const task = previous
      .catch(() => {})
      .then(async () => {
        saved[qid] = "saving";
        saved = { ...saved };
        let lastError: unknown;
        for (let attemptNo = 0; attemptNo < 3; attemptNo += 1) {
          try {
            await api.put(`/attempts/${attemptId}/answers/${qid}`, { answer_text: value });
            if ((revisions[qid] ?? 0) === revision) {
              saved[qid] = "saved";
              saved = { ...saved };
            }
            return;
          } catch (e) {
            lastError = e;
            if (!isTransient(e) || attemptNo === 2) break;
            await new Promise((resolve) => setTimeout(resolve, 250 * 2 ** attemptNo));
          }
        }
        saved[qid] = "error";
        saved = { ...saved };
        if (required) throw lastError;
      });
    saveChains[qid] = task;
    return task;
  }

  async function retryFailed() {
    const failed = questions.filter((q) => saved[q.id] === "error");
    await Promise.allSettled(failed.map((q) => saveAnswer(q.id)));
  }

  function requestSubmit() {
    showSubmitModal = true;
  }

  async function executeSubmit() {
    if (submitting || finished) return;
    submitting = true;
    submitError = "";
    // Flush any pending autosave timers first, then save every answer.
    for (const qid of Object.keys(autosaveTimers)) {
      clearTimeout(autosaveTimers[qid]);
    }
    try {
      const pending = questions.filter(
        (q) => revisions[q.id] || saved[q.id] === "saving" || saved[q.id] === "error",
      );
      await Promise.all(pending.map((q) => saveAnswer(q.id, true)));
      await api.post(`/attempts/${attemptId}/submit`);
      if (ticker) clearInterval(ticker);
      finished = true;
      showSubmitModal = false;
      await goto(`/exams/${examId}/result?attempt=${attemptId}`);
    } catch (e) {
      submitError = failedCount
        ? `${failedCount} jawaban belum berhasil disimpan. Periksa koneksi lalu coba lagi.`
        : e instanceof ApiError
          ? e.message
          : "Gagal mengirim jawaban";
    } finally {
      submitting = false;
    }
  }

  async function goToQuestion(index: number) {
    current = Math.max(0, Math.min(questions.length - 1, index));
    await tick();
    document.getElementById(`question-${questions[current]?.id}`)?.focus();
  }

  function mmss(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }

  // --- proctoring telemetry (best-effort; never blocks the exam) ---
  function reportEvent(kind: string, detail?: Record<string, unknown>) {
    if (!attemptId || finished) return;
    api
      .post(`/attempts/${attemptId}/events`, {
        events: [{ kind, detail: detail ?? null }],
      })
      .catch(() => {
        /* telemetry is best-effort */
      });
  }
  function onVisibility() {
    reportEvent(document.hidden ? "visibility_hidden" : "focus");
  }
  function onBlur() {
    reportEvent("blur");
  }
  // Paste during an exam is a flagged violation kind on the backend.
  function onPaste(e: ClipboardEvent) {
    reportEvent("paste", { target: (e.target as HTMLElement)?.tagName ?? null });
  }

  onMount(() => {
    window.addEventListener("beforeunload", warnBeforeUnload);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    document.addEventListener("paste", onPaste);
    load();
  });
  onDestroy(() => {
    if (ticker) clearInterval(ticker);
    for (const qid of Object.keys(autosaveTimers)) clearTimeout(autosaveTimers[qid]);
    window.removeEventListener("beforeunload", warnBeforeUnload);
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("blur", onBlur);
    document.removeEventListener("paste", onPaste);
  });
</script>

<svelte:head><title>Pengerjaan — QLoot</title></svelte:head>

<div class="mx-auto min-h-screen max-w-6xl px-4 py-4 sm:px-6 sm:py-6">
  {#if loading}
    <p class="muted" role="status">Memuat pengerjaan…</p>
  {:else if error}
    <div class="card mx-auto mt-16 max-w-xl text-center">
      <Icon name="triangle-exclamation" size="24px" class="text-danger" />
      <h1 class="mt-3 font-display text-xl font-bold">Pengerjaan tidak dapat dimuat</h1>
      <p class="alert-error mt-3" role="alert">{error}</p>
      <div class="mt-4 flex flex-wrap justify-center gap-2">
        <button class="btn-primary" on:click={() => window.location.reload()}>Coba lagi</button>
        <a class="btn-ghost" href={`/exams/${examId}`}>Kembali ke detail ujian</a>
      </div>
    </div>
  {:else if exam && attempt}
    <div
      class="sticky top-0 z-20 mb-4 flex flex-wrap items-center justify-between gap-3 rounded-sm border px-4 py-3 surface clip-corner"
    >
      <div>
        <h1 class="hud font-display text-lg font-bold">{exam.title}</h1>
        <p class="text-xs muted mt-0.5">
          Terjawab: <span class="font-mono text-mint font-semibold">{answeredCount}</span> dari {questions.length}
          soal
        </p>
      </div>
      <div class="flex items-center gap-3">
        <span
          class="badge font-mono"
          role="timer"
          aria-label={`Sisa waktu ${mmss(secondsLeft)}`}
          class:badge-magenta={secondsLeft < 300}
          class:badge-amber={secondsLeft >= 300}
        >
          <Icon name="stopwatch" size="10px" />
          {mmss(secondsLeft)}
        </span>
        <button class="btn-primary" on:click={requestSubmit} disabled={submitting}>
          {#if submitting}<Icon name="spinner" spin size="12px" />{/if}
          {submitting ? "Mengirim…" : "Kumpulkan"}
        </button>
      </div>
    </div>

    {#if secondsLeft > 0 && secondsLeft <= 300}
      <div class="alert-error mb-4 flex items-center gap-2 !py-2 text-xs">
        <Icon name="alert-triangle" size="14px" />
        <span
          >Peringatan: Sisa waktu pengerjaan kurang dari 5 menit! Jawaban akan dikumpulkan otomatis
          saat waktu habis.</span
        >
      </div>
    {/if}

    {#if loadWarning}
      <div class="alert-error mb-4" role="alert">
        <span class="flex-1">{loadWarning}</span>
        <button class="btn-secondary !py-1 flex-none" on:click={() => window.location.reload()}>
          Muat ulang
        </button>
      </div>
    {/if}

    <div
      class="mb-4 flex flex-wrap items-center justify-between gap-2 text-xs"
      role="status"
      aria-live="polite"
    >
      <span class="muted">
        {savingCount > 0
          ? `Menyimpan ${savingCount} jawaban…`
          : failedCount > 0
            ? `${failedCount} jawaban gagal disimpan`
            : answeredCount > 0
              ? "Semua perubahan tersimpan"
              : "Jawaban akan tersimpan otomatis"}
      </span>
      {#if failedCount > 0}
        <button class="btn-ghost !py-1 text-xs" on:click={retryFailed}>Coba simpan lagi</button>
      {/if}
    </div>

    {#if submitError && !showSubmitModal}
      <div class="alert-error mb-4" role="alert" aria-live="assertive">
        <span class="flex-1">{submitError}</span>
        <button class="btn-secondary !py-1 flex-none" on:click={requestSubmit}>Kirim ulang</button>
      </div>
    {/if}

    <div class="grid gap-4 lg:grid-cols-[1fr_240px]">
      <div class="space-y-4">
        {#each questions as q, i}
          {#if i === current}
            <div class="card" id={`question-${q.id}`} tabindex="-1">
              <div class="flex flex-wrap items-center justify-between gap-2 border-b pb-3">
                <div class="flex items-center gap-2">
                  <h2 class="hud font-display text-lg font-bold">
                    Soal {i + 1} dari {questions.length}
                  </h2>
                  <span class="badge border-primary/30 text-primary text-[11px]">
                    {QTYPE_LABELS[q.qtype] ?? q.qtype}
                  </span>
                </div>
                <div class="flex items-center gap-3">
                  <button
                    type="button"
                    class="btn-ghost !py-1 !px-2.5 text-xs flex items-center gap-1.5 transition-colors border {flagged[
                      q.id
                    ]
                      ? '!border-amber-400 !text-amber-400 !bg-amber-400/10'
                      : ''}"
                    on:click={() => toggleFlag(q.id)}
                    aria-pressed={flagged[q.id] ?? false}
                    title="Tandai soal ini jika masih ragu-ragu"
                  >
                    <Icon name="flag" size="11px" />
                    <span>{flagged[q.id] ? "Ragu-ragu (Ditandai)" : "Tandai Ragu-ragu"}</span>
                  </button>
                  <span class="text-xs muted flex items-center gap-1 font-mono" aria-live="polite">
                    {#if saved[q.id] === "saving"}
                      <Icon name="spinner" spin size="10px" /> Menyimpan…
                    {:else if saved[q.id] === "saved"}
                      <span class="text-mint flex items-center gap-1"
                        >Tersimpan <Icon name="check" size="10px" /></span
                      >
                    {:else if saved[q.id] === "error"}
                      <span class="text-magenta">Gagal menyimpan</span>
                    {:else}
                      Belum tersimpan
                    {/if}
                  </span>
                </div>
              </div>
              <p class="mt-3" id={`prompt-${q.id}`}>{q.prompt}</p>
              {#if q.qtype === "multiple_choice"}
                <fieldset class="mt-3 space-y-2" aria-labelledby={`prompt-${q.id}`}>
                  {#each q.options ?? [] as opt}
                    <label
                      class="flex cursor-pointer items-center gap-3 rounded-sm border px-3 py-2 text-sm transition-colors"
                      class:border-primary={answers[q.id] === opt.label}
                      style={answers[q.id] === opt.label
                        ? "background-color: rgb(var(--accent) / 0.1)"
                        : ""}
                    >
                      <input
                        type="radio"
                        name={`q-${q.id}`}
                        value={opt.label}
                        checked={answers[q.id] === opt.label}
                        on:change={() => {
                          answers[q.id] = opt.label;
                          onInput(q.id);
                        }}
                      />
                      <span class="mono text-xs muted">{opt.label}.</span>
                      <span>{opt.text}</span>
                    </label>
                  {/each}
                </fieldset>
              {:else if q.qtype === "true_false"}
                <fieldset class="mt-3 space-y-2" aria-labelledby={`prompt-${q.id}`}>
                  {#each [["true", "Benar"], ["false", "Salah"]] as [val, label]}
                    <label
                      class="flex cursor-pointer items-center gap-3 rounded-sm border px-3 py-2 text-sm"
                      class:border-primary={answers[q.id] === val}
                    >
                      <input
                        type="radio"
                        name={`q-${q.id}`}
                        value={val}
                        checked={answers[q.id] === val}
                        on:change={() => {
                          answers[q.id] = val;
                          onInput(q.id);
                        }}
                      />
                      <span>{label}</span>
                    </label>
                  {/each}
                </fieldset>
              {:else if q.qtype === "multi_select"}
                <fieldset class="mt-3 space-y-2" aria-labelledby={`prompt-${q.id}`}>
                  {#each q.options ?? [] as opt}
                    <label
                      class="flex cursor-pointer items-center gap-3 rounded-sm border px-3 py-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        value={opt.label}
                        checked={multiSelections(q.id).includes(opt.label)}
                        on:change={(e) => {
                          const set = new Set(multiSelections(q.id));
                          if ((e.currentTarget as HTMLInputElement).checked) set.add(opt.label);
                          else set.delete(opt.label);
                          answers[q.id] = JSON.stringify([...set]);
                          onInput(q.id);
                        }}
                      />
                      <span class="mono text-xs muted">{opt.label}.</span>
                      <span>{opt.text}</span>
                    </label>
                  {/each}
                </fieldset>
              {:else if q.qtype === "numeric"}
                <input
                  class="input mt-3 w-full sm:!w-56"
                  type="number"
                  step="any"
                  placeholder="Jawaban angka…"
                  aria-labelledby={`prompt-${q.id}`}
                  value={answers[q.id] ?? ""}
                  on:input={(e) => {
                    answers[q.id] = (e.currentTarget as HTMLInputElement).value;
                    onInput(q.id);
                  }}
                />
              {:else if q.qtype === "fill_blank"}
                <input
                  class="input mt-3 w-full sm:!w-72"
                  placeholder="Jawaban singkat…"
                  aria-labelledby={`prompt-${q.id}`}
                  value={answers[q.id] ?? ""}
                  on:input={(e) => {
                    answers[q.id] = (e.currentTarget as HTMLInputElement).value;
                    onInput(q.id);
                  }}
                />
              {:else if q.qtype === "ordering"}
                <textarea
                  class="input mt-3 min-h-[120px]"
                  placeholder="Tulis item dalam urutan yang benar, satu per baris"
                  aria-labelledby={`prompt-${q.id}`}
                  value={orderingText(q.id)}
                  on:input={(e) => {
                    const lines = (e.currentTarget as HTMLTextAreaElement).value
                      .split("\n")
                      .map((s) => s.trim())
                      .filter(Boolean);
                    answers[q.id] = JSON.stringify(lines);
                    onInput(q.id);
                  }}
                ></textarea>
              {:else if q.qtype === "matching"}
                <textarea
                  class="input mt-3 min-h-[120px]"
                  placeholder="Pasangan kunci=nilai, satu per baris"
                  aria-labelledby={`prompt-${q.id}`}
                  value={matchingText(q.id)}
                  on:input={(e) => {
                    const obj: Record<string, string> = {};
                    for (const line of (e.currentTarget as HTMLTextAreaElement).value.split("\n")) {
                      const [k, v] = line.split("=");
                      if (k && v) obj[k.trim()] = v.trim();
                    }
                    answers[q.id] = JSON.stringify(obj);
                    onInput(q.id);
                  }}
                ></textarea>
              {:else}
                <textarea
                  class="input mt-3 min-h-[160px]"
                  placeholder="Tulis jawabanmu…"
                  aria-labelledby={`prompt-${q.id}`}
                  value={answers[q.id] ?? ""}
                  on:input={(e) => {
                    answers[q.id] = (e.currentTarget as HTMLTextAreaElement).value;
                    onInput(q.id);
                  }}
                ></textarea>
              {/if}
              <div class="mt-6 flex flex-wrap items-center justify-between gap-2 border-t pt-4">
                <button class="btn-ghost" disabled={i === 0} on:click={() => goToQuestion(i - 1)}>
                  ← Sebelumnya
                </button>
                <div class="flex items-center gap-2">
                  {#if i === questions.length - 1}
                    <button class="btn-primary" on:click={requestSubmit}>
                      Tinjau & Kumpulkan →
                    </button>
                  {:else}
                    <button class="btn-secondary" on:click={() => goToQuestion(i + 1)}>
                      Berikutnya →
                    </button>
                  {/if}
                </div>
              </div>
            </div>
          {/if}
        {/each}
      </div>

      <aside class="card h-fit space-y-4">
        <div>
          <h2 class="hud font-display text-base font-bold">Navigasi Soal</h2>
          <div class="mt-2 space-y-1">
            <div class="flex items-center justify-between text-xs">
              <span class="muted">Progres</span>
              <span class="font-mono text-primary font-bold"
                >{answeredCount}/{questions.length} ({progressPercent}%)</span
              >
            </div>
            <div
              class="track h-1.5 w-full"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax={questions.length}
              aria-valuenow={answeredCount}
              aria-valuetext={`${answeredCount} dari ${questions.length} soal terjawab`}
            >
              <span style={`width:${progressPercent}%`}></span>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-5 gap-2">
          {#each questions as q, i}
            {@const isCur = i === current}
            {@const isAns = isAnswered(q.id, answers)}
            {@const isFlag = flagged[q.id]}
            <button
              class="relative h-11 w-11 rounded-sm border font-mono text-sm font-medium transition-all {isCur
                ? 'border-primary bg-primary text-[#05060A]'
                : isFlag
                  ? 'border-amber-400 bg-amber-400/20 text-amber-300'
                  : isAns
                    ? 'border-secondary bg-secondary/10 text-secondary'
                    : 'border-border/60 opacity-60'}"
              on:click={() => goToQuestion(i)}
              aria-current={isCur ? "step" : undefined}
              aria-label={`Soal ${i + 1}, ${isAns ? "terjawab" : "belum dijawab"}${isFlag ? ", ditandai ragu-ragu" : ""}`}
              title={`Soal #${i + 1} (${isAns ? "Terjawab" : "Belum diisi"}${isFlag ? " · Ragu-ragu" : ""})`}
            >
              {i + 1}
              {#if isFlag}
                <span
                  class="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-amber-400 ring-2 ring-background"
                ></span>
              {/if}
            </button>
          {/each}
        </div>

        <div class="border-t pt-3 grid grid-cols-2 gap-2 text-[11px] muted">
          <div class="flex items-center gap-1.5">
            <span class="h-2.5 w-2.5 rounded-xs border border-secondary bg-secondary/20"></span>
            <span>Terjawab</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="h-2.5 w-2.5 rounded-xs border border-border bg-background opacity-60"
            ></span>
            <span>Belum diisi</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="h-2.5 w-2.5 rounded-xs border border-amber-400 bg-amber-400/30"></span>
            <span>Ragu-ragu</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="h-2.5 w-2.5 rounded-xs border border-primary bg-primary"></span>
            <span>Aktif</span>
          </div>
        </div>

        <button
          type="button"
          class="btn-primary w-full text-xs !py-2"
          on:click={requestSubmit}
          disabled={submitting}
        >
          Kumpulkan Ujian
        </button>
      </aside>
    </div>

    {#if showSubmitModal}
      <Dialog
        title="Konfirmasi Pengumpulan Ujian"
        description={exam.title}
        titleId="submit-modal-title"
        descriptionId="submit-modal-description"
        busy={submitting}
        close={() => (showSubmitModal = false)}
      >
        <div class="space-y-4">
          <div class="grid grid-cols-3 gap-2 text-center text-xs">
            <div class="rounded-sm border p-2.5 surface">
              <div class="mono-label text-[10px]">Total Soal</div>
              <div class="font-mono text-base font-bold mt-1">{questions.length}</div>
            </div>
            <div class="rounded-sm border p-2.5 surface">
              <div class="mono-label text-[10px]">Terjawab</div>
              <div class="font-mono text-base font-bold text-mint mt-1">{answeredCount}</div>
            </div>
            <div class="rounded-sm border p-2.5 surface">
              <div class="mono-label text-[10px]">Belum Diisi</div>
              <div
                class="font-mono text-base font-bold mt-1"
                class:text-magenta={unansweredCount > 0}
                class:muted={unansweredCount === 0}
              >
                {unansweredCount}
              </div>
            </div>
          </div>

          {#if unansweredCount > 0}
            <div
              class="rounded-sm border border-magenta/40 bg-magenta/10 p-3 text-xs text-magenta space-y-2"
            >
              <div class="flex items-center gap-1.5 font-bold">
                <Icon name="alert-triangle" size="14px" />
                <span>Masih ada {unansweredCount} soal yang belum dijawab!</span>
              </div>
              <p class="text-muted leading-relaxed">
                Klik nomor soal di bawah untuk langsung menuju soal tersebut sebelum mengumpulkan:
              </p>
              <div class="flex flex-wrap gap-1.5 pt-1">
                {#each questions as q, idx}
                  {#if !isAnswered(q.id, answers)}
                    <button
                      type="button"
                      class="h-7 px-2.5 rounded-xs border border-magenta/50 bg-background text-xs font-mono font-medium hover:bg-magenta/20 transition-colors"
                      on:click={() => {
                        showSubmitModal = false;
                        void goToQuestion(idx);
                      }}
                    >
                      #{idx + 1}
                    </button>
                  {/if}
                {/each}
              </div>
            </div>
          {:else}
            <div
              class="rounded-sm border border-mint/40 bg-mint/10 p-3 text-xs text-mint flex items-center gap-2"
            >
              <Icon name="check" size="14px" />
              <span>Semua soal telah terjawab. Anda siap menyelesaikan ujian!</span>
            </div>
          {/if}

          {#if flaggedCount > 0}
            <div
              class="rounded-sm border border-amber/40 bg-amber/10 p-2.5 text-xs text-amber flex items-center gap-2"
            >
              <Icon name="flag" size="12px" />
              <span>Terdapat {flaggedCount} soal yang masih Anda tandai ragu-ragu.</span>
            </div>
          {/if}

          {#if submitError}
            <div class="alert-error text-xs">
              <span>{submitError}</span>
            </div>
          {/if}
        </div>
        <svelte:fragment slot="footer">
          <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              class="btn-ghost text-xs"
              data-autofocus
              disabled={submitting}
              on:click={() => (showSubmitModal = false)}
            >
              Lanjut Mengerjakan
            </button>
            <button
              type="button"
              class="btn-primary text-xs"
              disabled={submitting}
              on:click={executeSubmit}
            >
              {#if submitting}<Icon name="spinner" spin size="12px" />{/if}
              {submitting ? "Mengirim Jawaban…" : "Ya, Kumpulkan Sekarang"}
            </button>
          </div>
        </svelte:fragment>
      </Dialog>
    {/if}
  {/if}
</div>
