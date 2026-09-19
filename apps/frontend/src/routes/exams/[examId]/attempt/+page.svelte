<script lang="ts">
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
  const autosaveTimers: Record<string, ReturnType<typeof setTimeout>> = {};

  const examId = $page.params.examId;
  const attemptId = $page.url.searchParams.get("attempt") ?? "";

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
      error = e instanceof ApiError ? e.message : "Failed to load attempt";
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
    if (ticker) clearInterval(ticker);
    // Flush pending answers.
    if (exam) {
      for (const q of exam.questions ?? []) await saveAnswer(q.id);
    }
    try {
      await api.post(`/attempts/${attemptId}/submit`);
      await goto(`/exams/${examId}/result?attempt=${attemptId}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Submit failed";
    }
  }

  function mmss(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }

  onMount(load);
  onDestroy(() => {
    if (ticker) clearInterval(ticker);
  });
</script>

<svelte:head><title>Attempt — QLoot</title></svelte:head>

{#if loading}
  <p class="muted">Loading attempt…</p>
{:else if error}
  <p class="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{:else if exam && attempt}
  <div
    class="sticky top-16 z-20 mb-4 flex items-center justify-between rounded-xl border px-4 py-3 surface"
  >
    <h1 class="font-semibold">{exam.title}</h1>
    <div class="flex items-center gap-3">
      <span
        class="badge"
        class:bg-red-100={secondsLeft < 60}
        class:text-red-700={secondsLeft < 60}
        class:bg-amber-100={secondsLeft >= 60}
        class:text-amber-700={secondsLeft >= 60}
      >
        ⏱ {mmss(secondsLeft)}
      </span>
      <button class="btn-primary" on:click={submit}>Submit</button>
    </div>
  </div>

  <div class="grid gap-4 lg:grid-cols-[1fr_220px]">
    <div class="space-y-4">
      {#each exam.questions ?? [] as q, i}
        {#if i === current}
          <div class="card">
            <div class="flex items-center justify-between">
              <h2 class="font-semibold">Question {i + 1} of {exam.questions?.length}</h2>
              <span class="text-xs muted">
                {#if saved[q.id] === "saving"}Saving…
                {:else if saved[q.id] === "saved"}Saved ✓
                {:else if saved[q.id] === "error"}Save failed
                {:else}Not saved{/if}
              </span>
            </div>
            <p class="mt-3">{q.prompt}</p>
            <textarea
              class="input mt-3 min-h-[160px]"
              placeholder="Write your answer…"
              value={answers[q.id] ?? ""}
              on:input={(e) => {
                answers[q.id] = (e.currentTarget as HTMLTextAreaElement).value;
                onInput(q.id);
              }}
            ></textarea>
            <div class="mt-3 flex justify-between">
              <button class="btn-ghost" disabled={i === 0} on:click={() => (current = i - 1)}
                >← Previous</button
              >
              <button
                class="btn-primary"
                disabled={i === (exam.questions?.length ?? 0) - 1}
                on:click={() => (current = i + 1)}>Next →</button
              >
            </div>
          </div>
        {/if}
      {/each}
    </div>

    <aside class="card h-fit">
      <h2 class="font-semibold">Navigator</h2>
      <div class="mt-3 grid grid-cols-5 gap-2">
        {#each exam.questions ?? [] as q, i}
          <button
            class="h-9 w-9 rounded-lg border text-sm"
            class:bg-primary-600={i === current}
            class:text-white={i === current}
            class:bg-green-100={saved[q.id] === "saved" && i !== current}
            on:click={() => (current = i)}
          >
            {i + 1}
          </button>
        {/each}
      </div>
      <p class="mt-3 text-xs muted">Green = saved. Click to jump.</p>
    </aside>
  </div>
{/if}
