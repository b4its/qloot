<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Question } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const examId = $page.params.id;

  let exam: Exam | null = null;
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";

  let form = { title: "", duration_minutes: 60, passing_score_bp: 6000 };

  let questions: Question[] = [];
  let questionsLoading = false;
  // New-question draft. ``qtype`` selects essay (AI-graded) or multiple_choice.
  type OptionDraft = { text: string; is_correct: boolean };
  const OPTION_LABELS = "ABCDEFGH";
  function blankOptions(): OptionDraft[] {
    return [
      { text: "", is_correct: true },
      { text: "", is_correct: false },
    ];
  }
  let newQ = { prompt: "", correct_answer: "", qtype: "essay", options: blankOptions() };
  let editingQ: string | null = null;
  let editQ = { prompt: "", correct_answer: "", qtype: "essay", options: blankOptions() };

  function addOption(list: OptionDraft[]) {
    if (list.length < 8) list.push({ text: "", is_correct: false });
  }
  function removeOption(list: OptionDraft[], i: number) {
    if (list.length <= 2) return;
    const wasCorrect = list[i].is_correct;
    list.splice(i, 1);
    if (wasCorrect && list.length) list[0].is_correct = true;
  }
  function setCorrect(list: OptionDraft[], i: number) {
    list.forEach((o, j) => (o.is_correct = j === i));
  }
  function validMc(list: OptionDraft[]): boolean {
    return (
      list.length >= 2 &&
      list.every((o) => o.text.trim().length > 0) &&
      list.filter((o) => o.is_correct).length === 1
    );
  }

  async function loadExam() {
    loading = true;
    try {
      exam = await api.get<Exam>(`/exams/${examId}`);
      form = {
        title: exam.title,
        duration_minutes: exam.duration_minutes,
        passing_score_bp: exam.passing_score_bp,
      };
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    } finally {
      loading = false;
    }
  }

  async function loadQuestions() {
    questionsLoading = true;
    try {
      const detail = await api.get<Exam>(`/exams/${examId}`);
      questions = detail.questions ?? [];
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat soal";
    } finally {
      questionsLoading = false;
    }
  }

  async function saveExam() {
    if (form.title.trim().length < 2) {
      error = "Judul ujian minimal 2 karakter.";
      return;
    }
    error = "";
    message = "";
    busy = "exam";
    try {
      exam = await api.patch<Exam>(`/exams/${examId}`, form);
      message = "Ujian diperbarui.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui ujian";
    } finally {
      busy = "";
    }
  }

  async function togglePublish() {
    if (!exam) return;
    error = "";
    busy = "publish";
    try {
      if (exam.is_active) await api.post(`/exams/${examId}/close`);
      else await api.post(`/exams/${examId}/publish`);
      await loadExam();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah status";
    } finally {
      busy = "";
    }
  }

  async function addQuestion() {
    if (newQ.prompt.trim().length < 5) {
      error = "Soal minimal 5 karakter.";
      return;
    }
    if (newQ.qtype === "multiple_choice" && !validMc(newQ.options)) {
      error = "Pilihan ganda butuh ≥2 opsi dan tepat satu jawaban benar.";
      return;
    }
    error = "";
    message = "";
    busy = "q-add";
    try {
      await api.post(`/exams/${examId}/questions`, {
        prompt: newQ.prompt.trim(),
        correct_answer: newQ.qtype === "essay" ? newQ.correct_answer.trim() || null : null,
        qtype: newQ.qtype,
        position: questions.length,
        options:
          newQ.qtype === "multiple_choice"
            ? newQ.options.map((o) => ({ text: o.text.trim(), is_correct: o.is_correct }))
            : [],
      });
      newQ = { prompt: "", correct_answer: "", qtype: "essay", options: blankOptions() };
      message = "Soal ditambahkan.";
      await loadQuestions();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menambah soal";
    } finally {
      busy = "";
    }
  }

  function startEditQ(q: Question) {
    editingQ = q.id;
    editQ = {
      prompt: q.prompt,
      correct_answer: q.correct_answer ?? "",
      qtype: q.qtype,
      options:
        q.qtype === "multiple_choice"
          ? (q.options ?? []).map((o) => ({ text: o.text, is_correct: !!o.is_correct }))
          : blankOptions(),
    };
  }

  async function saveQ() {
    if (!editingQ) return;
    if (editQ.prompt.trim().length < 5) {
      error = "Soal minimal 5 karakter.";
      return;
    }
    if (editQ.qtype === "multiple_choice" && !validMc(editQ.options)) {
      error = "Pilihan ganda butuh ≥2 opsi dan tepat satu jawaban benar.";
      return;
    }
    error = "";
    busy = "q-edit";
    try {
      await api.patch(`/questions/${editingQ}`, {
        prompt: editQ.prompt.trim(),
        correct_answer: editQ.qtype === "essay" ? editQ.correct_answer.trim() || null : null,
        options:
          editQ.qtype === "multiple_choice"
            ? editQ.options.map((o) => ({ text: o.text.trim(), is_correct: o.is_correct }))
            : undefined,
      });
      editingQ = null;
      message = "Soal diperbarui.";
      await loadQuestions();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui soal";
    } finally {
      busy = "";
    }
  }

  async function removeQ(q: Question) {
    if (!confirm("Hapus soal ini?")) return;
    error = "";
    message = "";
    busy = `qd-${q.id}`;
    try {
      await api.delete(`/questions/${q.id}`);
      message = "Soal dihapus.";
      await loadQuestions();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus soal";
    } finally {
      busy = "";
    }
  }

  onMount(() => {
    loadExam();
    loadQuestions();
  });
</script>

<svelte:head><title>Kelola Ujian — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Ujian"
    title={exam?.title ?? "Kelola ujian"}
    subtitle="Ubah detail ujian dan kelola soalnya."
    backHref="/teacher/exams"
    backLabel="Ujian"
    actionHref={`/teacher/exams/${examId}/results`}
    actionLabel="Hasil"
    actionIcon="chart-simple"
  />

  <PageAlerts {message} {error} />

  {#if loading}
    <div class="mt-6 space-y-3">
      <div class="skeleton h-40"></div>
      <div class="skeleton h-40"></div>
    </div>
  {:else if exam}
    <div class="card mt-6">
      <div class="flex items-center justify-between">
        <h2 class="hud font-display text-lg font-bold">Detail ujian</h2>
        <span class="badge" class:badge-mint={exam.is_active} class:badge-neutral={!exam.is_active}>
          {exam.is_active ? "Aktif" : "Draf"}
        </span>
      </div>
      <div class="mt-3 grid gap-3 sm:grid-cols-3">
        <label class="block sm:col-span-3">
          <span class="mono-label">Judul</span>
          <input class="input mt-1" bind:value={form.title} />
        </label>
        <label class="block">
          <span class="mono-label">Durasi (menit)</span>
          <input class="input mt-1" type="number" min="1" bind:value={form.duration_minutes} />
        </label>
        <label class="block">
          <span class="mono-label">Passing score (bp)</span>
          <input
            class="input mt-1"
            type="number"
            min="0"
            max="10000"
            bind:value={form.passing_score_bp}
          />
        </label>
      </div>
      <div class="mt-3 flex items-center justify-between">
        <button class="btn-secondary" on:click={togglePublish} disabled={busy === "publish"}>
          {exam.is_active ? "Tutup ujian" : "Terbitkan ujian"}
        </button>
        <button class="btn-primary" on:click={saveExam} disabled={busy === "exam"}>
          {busy === "exam" ? "Menyimpan…" : "Simpan perubahan"}
        </button>
      </div>
    </div>

    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Soal ({questions.length})</h2>
      {#if questionsLoading}
        <div class="mt-3 space-y-2">
          {#each Array(2) as _}<div class="skeleton h-8"></div>{/each}
        </div>
      {:else}
        <ol class="mt-3 space-y-2 text-sm">
          {#each questions as q, i}
            {#if editingQ === q.id}
              <li class="border-b pb-2 last:border-0">
                <input class="input" bind:value={editQ.prompt} />
                {#if editQ.qtype === "multiple_choice"}
                  <div class="mt-2 space-y-2">
                    {#each editQ.options as opt, oi}
                      <div class="flex items-center gap-2">
                        <button
                          type="button"
                          class="btn-icon flex-none"
                          class:!border-secondary={opt.is_correct}
                          class:!text-secondary={opt.is_correct}
                          title="Tandai jawaban benar"
                          on:click={() => setCorrect(editQ.options, oi)}
                        >
                          <Icon name={opt.is_correct ? "circle-check" : "circle"} size="11px" />
                        </button>
                        <span class="mono text-xs muted">{OPTION_LABELS[oi]}</span>
                        <input
                          class="input !py-1"
                          bind:value={opt.text}
                          placeholder="Teks pilihan"
                        />
                        <button
                          type="button"
                          class="btn-icon !text-tertiary flex-none"
                          on:click={() => removeOption(editQ.options, oi)}
                          disabled={editQ.options.length <= 2}
                          aria-label="Hapus pilihan"
                        >
                          <Icon name="xmark" size="11px" />
                        </button>
                      </div>
                    {/each}
                    <button
                      type="button"
                      class="btn-ghost !py-1 text-xs"
                      on:click={() => addOption(editQ.options)}
                    >
                      <Icon name="plus" size="10px" /> Tambah pilihan
                    </button>
                  </div>
                {:else}
                  <textarea
                    class="input mt-2 min-h-[60px]"
                    placeholder="Kunci jawaban"
                    bind:value={editQ.correct_answer}
                  ></textarea>
                {/if}
                <div class="mt-2 flex gap-2">
                  <button class="btn-primary !py-1.5" on:click={saveQ} disabled={busy === "q-edit"}
                    >Simpan</button
                  >
                  <button class="btn-ghost !py-1.5" on:click={() => (editingQ = null)}>Batal</button
                  >
                </div>
              </li>
            {:else}
              <li class="flex items-start justify-between gap-2 border-b pb-1 last:border-0">
                <span
                  >{i + 1}.
                  <span class="badge badge-indigo"
                    >{q.qtype === "multiple_choice" ? "PG" : "Esai"}</span
                  >
                  {q.prompt}
                  {#if q.qtype === "multiple_choice" && q.options?.length}
                    <ul class="mt-1 space-y-0.5 text-xs muted">
                      {#each q.options as opt}
                        <li>
                          <span class="mono" class:text-secondary={opt.is_correct}
                            >{opt.label}.</span
                          >
                          <span class:text-secondary={opt.is_correct}>{opt.text}</span>
                          {#if opt.is_correct}<Icon name="circle-check" size="10px" />{/if}
                        </li>
                      {/each}
                    </ul>
                  {:else if q.correct_answer}
                    <span class="block text-xs muted">Kunci: {q.correct_answer}</span>
                  {/if}</span
                >
                <span class="flex flex-none gap-1">
                  <button class="btn-icon" on:click={() => startEditQ(q)} aria-label="Sunting soal"
                    ><Icon name="pen" size="11px" /></button
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
          {#if questions.length === 0}<li class="muted">Belum ada soal.</li>{/if}
        </ol>

        <div class="mt-3 space-y-2 border-t pt-3">
          <div class="flex items-center gap-2">
            <span class="mono-label">Tipe soal</span>
            <select class="input !w-auto !py-1" bind:value={newQ.qtype}>
              <option value="essay">Esai (dinilai AI)</option>
              <option value="multiple_choice">Pilihan ganda</option>
            </select>
          </div>
          <input class="input" placeholder="Pertanyaan baru" bind:value={newQ.prompt} />
          {#if newQ.qtype === "multiple_choice"}
            <div class="space-y-2">
              {#each newQ.options as opt, oi}
                <div class="flex items-center gap-2">
                  <button
                    type="button"
                    class="btn-icon flex-none"
                    class:!border-secondary={opt.is_correct}
                    class:!text-secondary={opt.is_correct}
                    title="Tandai jawaban benar"
                    on:click={() => setCorrect(newQ.options, oi)}
                  >
                    <Icon name={opt.is_correct ? "circle-check" : "circle"} size="11px" />
                  </button>
                  <span class="mono text-xs muted">{OPTION_LABELS[oi]}</span>
                  <input class="input !py-1" bind:value={opt.text} placeholder="Teks pilihan" />
                  <button
                    type="button"
                    class="btn-icon !text-tertiary flex-none"
                    on:click={() => removeOption(newQ.options, oi)}
                    disabled={newQ.options.length <= 2}
                    aria-label="Hapus pilihan"
                  >
                    <Icon name="xmark" size="11px" />
                  </button>
                </div>
              {/each}
              <button
                type="button"
                class="btn-ghost !py-1 text-xs"
                on:click={() => addOption(newQ.options)}
              >
                <Icon name="plus" size="10px" /> Tambah pilihan
              </button>
            </div>
          {:else}
            <textarea
              class="input min-h-[70px]"
              placeholder="Kunci jawaban / acuan"
              bind:value={newQ.correct_answer}
            ></textarea>
          {/if}
          <button class="btn-primary" on:click={addQuestion} disabled={busy === "q-add"}>
            {#if busy === "q-add"}<Icon name="spinner" spin size="12px" />{:else}<Icon
                name="plus"
                size="12px"
              />{/if}
            Tambah soal
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
