<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount, onDestroy } from "svelte";
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
  let finished = false;
  const autosaveTimers: Record<string, ReturnType<typeof setTimeout>> = {};

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

  function warnBeforeUnload(e: BeforeUnloadEvent) {
    if (finished || secondsLeft <= 0) return;
    e.preventDefault();
    e.returnValue = "";
  }

  async function load() {
    try {
      exam = await api.get<Exam>(`/exams/${examId}`);
      attempt = await api.get<Attempt>(`/attempts/${attemptId}`);
      // Prefer the attempt-scoped (shuffled) question set.
      questions = await api
        .get<NonNullable<Exam["questions"]>>(`/attempts/${attemptId}/questions`)
        .catch(() => exam?.questions ?? []);
      const res = await api.get<{ answers: Answer[] }>(`/attempts/${attemptId}/result`);
      for (const a of res.answers) {
        if (a.answer_text) {
          answers[a.question_id] = a.answer_text;
          saved[a.question_id] = "saved";
        }
      }
      answers = { ...answers };
      saved = { ...saved };
      startTimer();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
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
      secondsLeft = Math.max(0, Math.round((deadline - Date.now()) / 1000));
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
    saved[qid] = "idle";
    saved = { ...saved };
    if (autosaveTimers[qid]) clearTimeout(autosaveTimers[qid]);
    autosaveTimers[qid] = setTimeout(() => saveAnswer(qid), 800);
  }

  async function saveAnswer(qid: string) {
    saved[qid] = "saving";
    saved = { ...saved };
    try {
      await api.put(`/attempts/${attemptId}/answers/${qid}`, { answer_text: answers[qid] ?? "" });
      saved[qid] = "saved";
      saved = { ...saved };
    } catch {
      saved[qid] = "error";
      saved = { ...saved };
    }
  }

  function requestSubmit() {
    showSubmitModal = true;
  }

  async function executeSubmit() {
    if (submitting || finished) return;
    submitting = true;
    submitError = "";
    if (ticker) clearInterval(ticker);
    // Flush any pending autosave timers first, then save every answer.
    for (const qid of Object.keys(autosaveTimers)) {
      clearTimeout(autosaveTimers[qid]);
    }
    try {
      if (exam) {
        for (const q of questions) await saveAnswer(q.id);
      }
      await api.post(`/attempts/${attemptId}/submit`);
      finished = true;
      showSubmitModal = false;
      await goto(`/exams/${examId}/result?attempt=${attemptId}`);
    } catch (e) {
      submitError = e instanceof ApiError ? e.message : "Gagal mengirim jawaban";
    } finally {
      submitting = false;
    }
  }

  const submit = requestSubmit;

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

<div class="mx-auto max-w-5xl px-4 py-8 sm:px-6">
  {#if loading}
    <p class="muted">Memuat pengerjaan…</p>
  {:else if error}
    <p class="alert-error">
      {error}
    </p>
  {:else if exam && attempt}
    <div
      class="sticky top-16 z-20 mb-4 flex flex-wrap items-center justify-between gap-3 rounded-sm border px-4 py-3 surface clip-corner"
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

    {#if submitError}
      <div class="alert-error mb-4">
        <span class="flex-1">{submitError}</span>
        <button class="btn-secondary !py-1 flex-none" on:click={requestSubmit}>Coba lagi</button>
      </div>
    {/if}

    <div class="grid gap-4 lg:grid-cols-[1fr_240px]">
      <div class="space-y-4">
        {#each questions as q, i}
          {#if i === current}
            <div class="card">
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
                    title="Tandai soal ini jika masih ragu-ragu"
                  >
                    <Icon name="flag" size="11px" />
                    <span>{flagged[q.id] ? "Ragu-ragu (Ditandai)" : "Tandai Ragu-ragu"}</span>
                  </button>
                  <span class="text-xs muted flex items-center gap-1 font-mono">
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
              <p class="mt-3">{q.prompt}</p>
              {#if q.qtype === "multiple_choice"}
                <div class="mt-3 space-y-2">
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
                </div>
              {:else if q.qtype === "true_false"}
                <div class="mt-3 space-y-2">
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
                </div>
              {:else if q.qtype === "multi_select"}
                <div class="mt-3 space-y-2">
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
                </div>
              {:else if q.qtype === "numeric"}
                <input
                  class="input mt-3 !w-56"
                  type="number"
                  step="any"
                  placeholder="Jawaban angka…"
                  value={answers[q.id] ?? ""}
                  on:input={(e) => {
                    answers[q.id] = (e.currentTarget as HTMLInputElement).value;
                    onInput(q.id);
                  }}
                />
              {:else if q.qtype === "fill_blank"}
                <input
                  class="input mt-3 !w-72"
                  placeholder="Jawaban singkat…"
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
                  value={answers[q.id] ?? ""}
                  on:input={(e) => {
                    answers[q.id] = (e.currentTarget as HTMLTextAreaElement).value;
                    onInput(q.id);
                  }}
                ></textarea>
              {/if}
              <div class="mt-6 flex flex-wrap items-center justify-between gap-2 border-t pt-4">
                <button class="btn-ghost" disabled={i === 0} on:click={() => (current = i - 1)}>
                  ← Sebelumnya
                </button>
                <div class="flex items-center gap-2">
                  {#if i === questions.length - 1}
                    <button class="btn-primary" on:click={requestSubmit}>
                      Tinjau & Kumpulkan →
                    </button>
                  {:else}
                    <button class="btn-secondary" on:click={() => (current = i + 1)}>
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
            <div class="track h-1.5 w-full">
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
              class="relative h-9 w-9 rounded-sm border font-mono text-sm font-medium transition-all {isCur
                ? 'border-primary bg-primary text-[#05060A]'
                : isFlag
                  ? 'border-amber-400 bg-amber-400/20 text-amber-300'
                  : isAns
                    ? 'border-secondary bg-secondary/10 text-secondary'
                    : 'border-border/60 opacity-60'}"
              on:click={() => (current = i)}
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
      <div
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs"
        role="dialog"
        aria-modal="true"
        aria-labelledby="submit-modal-title"
      >
        <div class="card w-full max-w-lg space-y-4 border-primary/40 shadow-2xl">
          <div class="flex items-start justify-between border-b pb-3">
            <div>
              <h2 id="submit-modal-title" class="hud font-display text-lg font-bold">
                Konfirmasi Pengumpulan Ujian
              </h2>
              <p class="text-xs muted mt-0.5">{exam.title}</p>
            </div>
            <button
              class="text-muted hover:text-foreground text-sm"
              on:click={() => (showSubmitModal = false)}
              aria-label="Tutup">✕</button
            >
          </div>

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
                        current = idx;
                        showSubmitModal = false;
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

          <div class="flex items-center justify-end gap-2 border-t pt-3">
            <button
              type="button"
              class="btn-ghost text-xs"
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
        </div>
      </div>
    {/if}
  {/if}
</div>
