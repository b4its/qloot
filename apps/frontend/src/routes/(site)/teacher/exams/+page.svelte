<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Question, Attempt } from "$lib/types";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";

  const PAGE = 20;
  let exams: Exam[] = [];
  let results: Record<string, Attempt[]> = {};
  let newExam = { title: "", duration_minutes: 60, passing_score_bp: 6000 };
  let message = "";
  let error = "";
  let loading = true;
  let busy = "";
  let showResults: string | null = null;
  let page = 1;
  let hasMore = false;

  // Inline question authoring (replaces window.prompt).
  let addingFor: string | null = null;
  let qPrompt = "";
  let qAnswer = "";

  // Question manager (view/edit/delete a question).
  let questionsFor: string | null = null;
  let questions: Question[] = [];
  let questionsLoading = false;
  let editingQ: string | null = null;
  let editQ = { prompt: "", correct_answer: "" };

  // Inline exam editing.
  let editingId: string | null = null;
  let editForm = { title: "", duration_minutes: 60, passing_score_bp: 6000 };

  async function load() {
    loading = true;
    try {
      exams = await api.get<Exam[]>(`/exams?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = exams.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    page = next;
    load();
  }

  async function create() {
    error = "";
    message = "";
    busy = "create";
    try {
      const exam = await api.post<Exam>("/exams", newExam);
      message = `Ujian "${exam.title}" dibuat.`;
      newExam = { title: "", duration_minutes: 60, passing_score_bp: 6000 };
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat ujian";
    } finally {
      busy = "";
    }
  }

  function startAdd(exam: Exam) {
    addingFor = exam.id;
    qPrompt = "";
    qAnswer = "";
    error = "";
  }

  async function submitQuestion(exam: Exam) {
    if (qPrompt.trim().length < 5) {
      error = "Soal minimal 5 karakter.";
      return;
    }
    error = "";
    busy = `q-${exam.id}`;
    try {
      await api.post(`/exams/${exam.id}/questions`, {
        prompt: qPrompt.trim(),
        correct_answer: qAnswer.trim(),
        position: exam.questions?.length ?? 0,
      });
      message = "Soal ditambahkan.";
      addingFor = null;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menambah soal";
    } finally {
      busy = "";
    }
  }

  function startEdit(exam: Exam) {
    editingId = exam.id;
    editForm = {
      title: exam.title,
      duration_minutes: exam.duration_minutes,
      passing_score_bp: exam.passing_score_bp,
    };
    error = "";
  }

  async function saveEdit(exam: Exam) {
    error = "";
    busy = `e-${exam.id}`;
    try {
      await api.patch(`/exams/${exam.id}`, editForm);
      message = "Ujian diperbarui.";
      editingId = null;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui ujian";
    } finally {
      busy = "";
    }
  }

  async function togglePublish(exam: Exam) {
    error = "";
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

  async function viewResults(exam: Exam) {
    if (showResults === exam.id) {
      showResults = null;
      return;
    }
    error = "";
    try {
      results[exam.id] = await api.get<Attempt[]>(`/exams/${exam.id}/results`);
      showResults = exam.id;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat hasil";
    }
  }

  async function removeExam(exam: Exam) {
    if (!confirm(`Hapus ujian "${exam.title}"?`)) return;
    error = "";
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

  async function toggleQuestions(exam: Exam) {
    if (questionsFor === exam.id) {
      questionsFor = null;
      return;
    }
    questionsFor = exam.id;
    editingQ = null;
    questionsLoading = true;
    error = "";
    try {
      const detail = await api.get<Exam>(`/exams/${exam.id}`);
      questions = detail.questions ?? [];
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat soal";
    } finally {
      questionsLoading = false;
    }
  }

  function startEditQ(q: Question) {
    editingQ = q.id;
    editQ = { prompt: q.prompt, correct_answer: q.correct_answer ?? "" };
  }

  async function saveQ() {
    if (!editingQ) return;
    if (editQ.prompt.trim().length < 5) {
      error = "Soal minimal 5 karakter.";
      return;
    }
    busy = "q-edit";
    error = "";
    try {
      await api.patch(`/questions/${editingQ}`, {
        prompt: editQ.prompt.trim(),
        correct_answer: editQ.correct_answer.trim() || null,
      });
      if (questionsFor) {
        const detail = await api.get<Exam>(`/exams/${questionsFor}`);
        questions = detail.questions ?? [];
      }
      editingQ = null;
      message = "Soal diperbarui.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui soal";
    } finally {
      busy = "";
    }
  }

  async function removeQ(q: Question) {
    if (!confirm("Hapus soal ini?")) return;
    busy = `qd-${q.id}`;
    error = "";
    try {
      await api.delete(`/questions/${q.id}`);
      questions = questions.filter((x) => x.id !== q.id);
      message = "Soal dihapus.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus soal";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Ujian Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <p class="mono-label">Panel Guru · Ujian</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Kelola Ujian</h1>
  <p class="mt-2 muted">Buat ujian, tambah soal, sunting, dan publikasikan ke kelas.</p>

  {#if message}<p class="alert-ok mt-4">
      {message}
    </p>{/if}
  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  <div class="card mt-6">
    <h2 class="hud font-display text-lg font-bold">Ujian baru</h2>
    <div class="mt-3 grid gap-3 sm:grid-cols-3">
      <input class="input sm:col-span-1" placeholder="Judul" bind:value={newExam.title} />
      <input class="input" type="number" min="1" bind:value={newExam.duration_minutes} />
      <input
        class="input"
        type="number"
        min="0"
        max="10000"
        bind:value={newExam.passing_score_bp}
      />
    </div>
    <p class="mt-1 text-xs muted">Durasi (menit) · passing score dalam basis points (6000 = 60%)</p>
    <button
      class="btn-primary mt-3"
      on:click={create}
      disabled={newExam.title.length < 2 || busy === "create"}
    >
      {#if busy === "create"}<Icon name="spinner" spin size="12px" />{/if} Buat ujian
    </button>
  </div>

  {#if loading}
    <div class="mt-6 space-y-3">
      {#each Array(3) as _}<div class="skeleton h-28"></div>{/each}
    </div>
  {:else if exams.length === 0}
    <div class="card mt-6 grid place-items-center py-12 text-center">
      <Icon name="file-pen" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada ujian</p>
      <p class="text-sm muted">Buat ujian pertama dengan formulir di atas.</p>
    </div>
  {:else}
    <div class="mt-6 space-y-4">
      {#each exams as exam (exam.id)}
        <div class="card">
          {#if editingId === exam.id}
            <div class="grid gap-3 sm:grid-cols-3">
              <input class="input sm:col-span-1" bind:value={editForm.title} />
              <input class="input" type="number" min="1" bind:value={editForm.duration_minutes} />
              <input
                class="input"
                type="number"
                min="0"
                max="10000"
                bind:value={editForm.passing_score_bp}
              />
            </div>
            <div class="mt-3 flex gap-2">
              <button
                class="btn-primary"
                on:click={() => saveEdit(exam)}
                disabled={busy === `e-${exam.id}`}>Simpan</button
              >
              <button class="btn-ghost" on:click={() => (editingId = null)}>Batal</button>
            </div>
          {:else}
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 class="font-display text-lg font-bold">
                  {exam.title}
                  <span
                    class="badge ml-1"
                    class:badge-mint={exam.is_active}
                    class:badge-neutral={!exam.is_active}
                  >
                    {exam.is_active ? "Aktif" : "Draf"}
                  </span>
                </h2>
                <p class="text-sm muted">
                  {exam.questions?.length ?? 0} soal · {exam.duration_minutes} menit · lulus {(
                    exam.passing_score_bp / 100
                  ).toFixed(0)}%
                </p>
              </div>
              <div class="flex flex-wrap gap-2">
                <button class="btn-ghost" on:click={() => startAdd(exam)}>＋ Soal</button>
                <button class="btn-ghost" on:click={() => toggleQuestions(exam)}>Soal</button>
                <button class="btn-ghost" on:click={() => startEdit(exam)}>Sunting</button>
                <button class="btn-ghost" on:click={() => viewResults(exam)}>Hasil</button>
                <button
                  class="btn-primary"
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
          {/if}

          {#if questionsFor === exam.id}
            <div class="mt-3 border-t pt-3">
              <h3 class="mono-label">Daftar soal</h3>
              {#if questionsLoading}
                <div class="mt-2 space-y-2">
                  {#each Array(2) as _}<div class="skeleton h-8"></div>{/each}
                </div>
              {:else if questions.length === 0}
                <p class="mt-2 text-sm muted">Belum ada soal.</p>
              {:else}
                <ol class="mt-2 space-y-2 text-sm">
                  {#each questions as q, i}
                    {#if editingQ === q.id}
                      <li class="border-b pb-2 last:border-0">
                        <input class="input" bind:value={editQ.prompt} />
                        <textarea
                          class="input mt-2 min-h-[60px]"
                          placeholder="Kunci jawaban"
                          bind:value={editQ.correct_answer}
                        ></textarea>
                        <div class="mt-2 flex gap-2">
                          <button
                            class="btn-primary !py-1.5"
                            on:click={saveQ}
                            disabled={busy === "q-edit"}>Simpan</button
                          >
                          <button class="btn-ghost !py-1.5" on:click={() => (editingQ = null)}
                            >Batal</button
                          >
                        </div>
                      </li>
                    {:else}
                      <li
                        class="flex items-start justify-between gap-2 border-b pb-1 last:border-0"
                      >
                        <span
                          >{i + 1}. {q.prompt}
                          {#if q.correct_answer}<span class="block text-xs muted"
                              >Kunci: {q.correct_answer}</span
                            >{/if}</span
                        >
                        <span class="flex flex-none gap-1">
                          <button
                            class="btn-icon"
                            on:click={() => startEditQ(q)}
                            aria-label="Sunting soal"><Icon name="pen" size="11px" /></button
                          >
                          <button
                            class="btn-icon !text-tertiary hover:!border-tertiary"
                            on:click={() => removeQ(q)}
                            disabled={busy === `qd-${q.id}`}
                            aria-label="Hapus soal"><Icon name="trash" size="11px" /></button
                          >
                        </span>
                      </li>
                    {/if}
                  {/each}
                </ol>
              {/if}
            </div>
          {/if}

          {#if addingFor === exam.id}
            <div class="mt-3 space-y-2 border-t pt-3">
              <input class="input" placeholder="Pertanyaan" bind:value={qPrompt} />
              <textarea
                class="input min-h-[70px]"
                placeholder="Kunci jawaban / acuan"
                bind:value={qAnswer}
              ></textarea>
              <div class="flex gap-2">
                <button
                  class="btn-primary"
                  on:click={() => submitQuestion(exam)}
                  disabled={busy === `q-${exam.id}`}
                >
                  {#if busy === `q-${exam.id}`}<Icon name="spinner" spin size="12px" />{/if} Tambah soal
                </button>
                <button class="btn-ghost" on:click={() => (addingFor = null)}>Batal</button>
              </div>
            </div>
          {/if}

          {#if showResults === exam.id}
            <div class="mt-3 border-t pt-3">
              <h3 class="mono-label">Hasil peserta</h3>
              <ul class="mt-1 space-y-1 text-sm">
                {#each results[exam.id] ?? [] as a}
                  <li class="flex justify-between">
                    <span class="font-mono">{a.user_id.slice(0, 8)}…</span>
                    <span
                      >{a.score_bp !== null && a.score_bp !== undefined
                        ? (a.score_bp / 100).toFixed(1) + "%"
                        : a.status}</span
                    >
                  </li>
                {/each}
                {#if !results[exam.id]?.length}<li class="muted">Belum ada pengumpulan.</li>{/if}
              </ul>
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <Pagination
      {page}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="ujian"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {/if}
</div>
