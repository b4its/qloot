<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount, onDestroy } from "svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Attempt, Answer } from "$lib/types";

  let exam: Exam | null = null;
  let attempt: Attempt | null = null;
  let answers: Record<string, string> = {};
  let saved: Record<string, "idle" | "saving" | "saved" | "error"> = {};
  let loading = true;
  let error = "";
  let current = 0;
  let secondsLeft = 0;
  let ticker: ReturnType<typeof setInterval> | null = null;
  let submitting = false;
  let submitError = "";
  let finished = false;
  const autosaveTimers: Record<string, ReturnType<typeof setTimeout>> = {};

  const examId = $page.params.examId;
  const attemptId = $page.url.searchParams.get("attempt") ?? "";

  function warnBeforeUnload(e: BeforeUnloadEvent) {
    if (finished || secondsLeft <= 0) return;
    e.preventDefault();
    e.returnValue = "";
  }

  async function load() {
    try {
      exam = await api.get<Exam>(`/exams/${examId}`);
      attempt = await api.get<Attempt>(`/attempts/${attemptId}`);
      const res = await api.get<{ answers: Answer[] }>(`/attempts/${attemptId}/result`);
      for (const a of res.answers) {
        if (a.answer_text) {
          answers[a.question_id] = a.answer_text;
          saved[a.question_id] = "saved";
        }
      }
      startTimer();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    } finally {
      loading = false;
    }
  }

  function startTimer() {
    if (!exam || !attempt) return;
    const deadline = new Date(attempt.started_at).getTime() + exam.duration_minutes * 60_000;
    const update = () => {
      secondsLeft = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      if (secondsLeft === 0) {
        if (ticker) clearInterval(ticker);
        submit();
      }
    };
    update();
    ticker = setInterval(update, 1000);
  }

  function onInput(qid: string) {
    saved[qid] = "idle";
    if (autosaveTimers[qid]) clearTimeout(autosaveTimers[qid]);
    autosaveTimers[qid] = setTimeout(() => saveAnswer(qid), 800);
  }

  async function saveAnswer(qid: string) {
    saved[qid] = "saving";
    try {
      await api.put(`/attempts/${attemptId}/answers/${qid}`, { answer_text: answers[qid] ?? "" });
      saved[qid] = "saved";
    } catch {
      saved[qid] = "error";
    }
  }

  async function submit() {
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
        for (const q of exam.questions ?? []) await saveAnswer(q.id);
      }
      await api.post(`/attempts/${attemptId}/submit`);
      finished = true;
      await goto(`/exams/${examId}/result?attempt=${attemptId}`);
    } catch (e) {
      submitError = e instanceof ApiError ? e.message : "Gagal mengirim jawaban";
    } finally {
      submitting = false;
    }
  }

  function mmss(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }

  onMount(() => {
    window.addEventListener("beforeunload", warnBeforeUnload);
    load();
  });
  onDestroy(() => {
    if (ticker) clearInterval(ticker);
    for (const qid of Object.keys(autosaveTimers)) clearTimeout(autosaveTimers[qid]);
    window.removeEventListener("beforeunload", warnBeforeUnload);
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
      class="sticky top-16 z-20 mb-4 flex items-center justify-between rounded-sm border px-4 py-3 surface clip-corner"
    >
      <h1 class="hud font-display text-lg font-bold">{exam.title}</h1>
      <div class="flex items-center gap-3">
        <span
          class="badge"
          class:badge-magenta={secondsLeft < 60}
          class:badge-amber={secondsLeft >= 60}
        >
          <Icon name="stopwatch" size="10px" />
          {mmss(secondsLeft)}
        </span>
        <button class="btn-primary" on:click={submit} disabled={submitting}>
          {#if submitting}<Icon name="spinner" spin size="12px" />{/if}
          {submitting ? "Mengirim…" : "Kumpulkan"}
        </button>
      </div>
    </div>

    {#if submitError}
      <div class="alert-error mb-4">
        <span class="flex-1">{submitError}</span>
        <button class="btn-secondary !py-1 flex-none" on:click={submit}>Coba lagi</button>
      </div>
    {/if}

    <div class="grid gap-4 lg:grid-cols-[1fr_220px]">
      <div class="space-y-4">
        {#each exam.questions ?? [] as q, i}
          {#if i === current}
            <div class="card">
              <div class="flex items-center justify-between">
                <h2 class="hud font-display text-lg font-bold">
                  Soal {i + 1} dari {exam.questions?.length}
                </h2>
                <span class="text-xs muted">
                  {#if saved[q.id] === "saving"}Menyimpan…
                  {:else if saved[q.id] === "saved"}Tersimpan <Icon name="check" size="10px" />
                  {:else if saved[q.id] === "error"}Gagal menyimpan
                  {:else}Belum tersimpan{/if}
                </span>
              </div>
              <p class="mt-3">{q.prompt}</p>
              <textarea
                class="input mt-3 min-h-[160px]"
                placeholder="Tulis jawabanmu…"
                value={answers[q.id] ?? ""}
                on:input={(e) => {
                  answers[q.id] = (e.currentTarget as HTMLTextAreaElement).value;
                  onInput(q.id);
                }}
              ></textarea>
              <div class="mt-3 flex justify-between">
                <button class="btn-ghost" disabled={i === 0} on:click={() => (current = i - 1)}
                  >← Sebelumnya</button
                >
                <button
                  class="btn-primary"
                  disabled={i === (exam.questions?.length ?? 0) - 1}
                  on:click={() => (current = i + 1)}>Berikutnya →</button
                >
              </div>
            </div>
          {/if}
        {/each}
      </div>

      <aside class="card h-fit">
        <h2 class="hud font-display text-lg font-bold">Navigasi</h2>
        <div class="mt-3 grid grid-cols-5 gap-2">
          {#each exam.questions ?? [] as q, i}
            <button
              class="h-9 w-9 rounded-sm border font-mono text-sm transition-colors"
              class:border-primary={i === current}
              class:bg-primary={i === current}
              class:text-[#05060A]={i === current}
              class:border-secondary={saved[q.id] === "saved" && i !== current}
              class:text-secondary={saved[q.id] === "saved" && i !== current}
              on:click={() => (current = i)}
            >
              {i + 1}
            </button>
          {/each}
        </div>
        <p class="mt-3 text-xs muted">Cyan = tersimpan. Klik untuk lompat.</p>
      </aside>
    </div>
  {/if}
</div>
