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

  let form = {
    title: "",
    duration_minutes: 60,
    passing_score_bp: 6000,
    max_attempts: 1,
    shuffle_questions: false,
    shuffle_options: false,
    grace_seconds: 0,
    late_penalty_bp: 0,
  };

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
  let newQ = {
    prompt: "",
    correct_answer: "",
    qtype: "essay",
    weight: 100,
    tf: "true",
    numericValue: 0,
    numericTolerance: 0,
    fillAnswers: "",
    orderItems: "",
    matchPairs: "",
    options: blankOptions(),
  };
  let editingQ: string | null = null;
  let editQ = {
    prompt: "",
    correct_answer: "",
    qtype: "essay",
    weight: 100,
    tf: "true",
    numericValue: 0,
    numericTolerance: 0,
    fillAnswers: "",
    orderItems: "",
    matchPairs: "",
    options: blankOptions(),
  };

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
  function validOptions(qtype: string, list: OptionDraft[]): boolean {
    if (list.length < 2 || !list.every((o) => o.text.trim().length > 0)) return false;
    const n = list.filter((o) => o.is_correct).length;
    return qtype === "multi_select" ? n >= 2 : n === 1;
  }

  type Draft = {
    prompt: string;
    correct_answer: string;
    qtype: string;
    weight: number;
    tf?: string;
    numericValue?: number;
    numericTolerance?: number;
    fillAnswers?: string;
    orderItems?: string;
    matchPairs?: string;
    options: OptionDraft[];
  };

  function buildQuestionPayload(d: Draft, position: number) {
    const base: Record<string, unknown> = {
      prompt: d.prompt.trim(),
      qtype: d.qtype,
      max_score_bp: Math.max(0, Math.min(10000, Math.round((d.weight ?? 100) * 100))),
      position,
    };
    if (d.qtype === "essay") {
      base.correct_answer = d.correct_answer.trim() || null;
    } else if (d.qtype === "true_false") {
      base.correct_answer = d.tf ?? "true";
    } else if (d.qtype === "multiple_choice" || d.qtype === "multi_select") {
      base.options = d.options.map((o) => ({ text: o.text.trim(), is_correct: o.is_correct }));
    } else if (d.qtype === "numeric") {
      base.answer_json = {
        value: Number(d.numericValue ?? 0),
        tolerance: Number(d.numericTolerance ?? 0),
      };
    } else if (d.qtype === "fill_blank") {
      base.answer_json = {
        accepted: (d.fillAnswers ?? "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        case_sensitive: false,
        trim: true,
      };
    } else if (d.qtype === "ordering") {
      base.answer_json = {
        order: (d.orderItems ?? "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      };
    } else if (d.qtype === "matching") {
      const pairs: Record<string, string> = {};
      for (const line of (d.matchPairs ?? "").split("\n")) {
        const [k, v] = line.split("=");
        if (k && v) pairs[k.trim()] = v.trim();
      }
      base.answer_json = { pairs };
    }
    return base;
  }

  async function loadExam() {
    loading = true;
    try {
      exam = await api.get<Exam>(`/exams/${examId}`);
      form = {
        title: exam.title,
        duration_minutes: exam.duration_minutes,
        passing_score_bp: exam.passing_score_bp,
        max_attempts: exam.max_attempts ?? 1,
        shuffle_questions: exam.shuffle_questions ?? false,
        shuffle_options: exam.shuffle_options ?? false,
        grace_seconds: exam.grace_seconds ?? 0,
        late_penalty_bp: exam.late_penalty_bp ?? 0,
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
    if (!(form.duration_minutes >= 1 && form.duration_minutes <= 600)) {
      error = "Durasi harus antara 1 dan 600 menit.";
      return;
    }
    if (!(form.passing_score_bp >= 0 && form.passing_score_bp <= 10000)) {
      error = "Passing score harus antara 0 dan 10000 bp.";
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
    if (
      (newQ.qtype === "multiple_choice" || newQ.qtype === "multi_select") &&
      !validOptions(newQ.qtype, newQ.options)
    ) {
      error = "Opsi tidak valid: minimal 2 opsi; PG tepat satu benar, pilih-banyak ≥2 benar.";
      return;
    }
    error = "";
    message = "";
    busy = "q-add";
    try {
      await api.post(`/exams/${examId}/questions`, buildQuestionPayload(newQ, questions.length));
      newQ = {
        prompt: "",
        correct_answer: "",
        qtype: "essay",
        weight: 100,
        tf: "true",
        numericValue: 0,
        numericTolerance: 0,
        fillAnswers: "",
        orderItems: "",
        matchPairs: "",
        options: blankOptions(),
      };
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
    const aj = (q as { answer_json?: Record<string, unknown> }).answer_json ?? {};
    editQ = {
      prompt: q.prompt,
      correct_answer: q.correct_answer ?? "",
      qtype: q.qtype,
      weight: Math.round((q.max_score_bp ?? 10000) / 100),
      tf: q.qtype === "true_false" ? (q.correct_answer ?? "true") : "true",
      numericValue: Number((aj.value as number) ?? 0),
      numericTolerance: Number((aj.tolerance as number) ?? 0),
      fillAnswers: Array.isArray(aj.accepted) ? (aj.accepted as string[]).join(", ") : "",
      orderItems: Array.isArray(aj.order) ? (aj.order as string[]).join("\n") : "",
      matchPairs:
        aj.pairs && typeof aj.pairs === "object"
          ? Object.entries(aj.pairs as Record<string, string>)
              .map(([k, v]) => `${k}=${v}`)
              .join("\n")
          : "",
      options:
        q.qtype === "multiple_choice" || q.qtype === "multi_select"
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
    if (
      (editQ.qtype === "multiple_choice" || editQ.qtype === "multi_select") &&
      !validOptions(editQ.qtype, editQ.options)
    ) {
      error = "Opsi tidak valid: minimal 2 opsi; PG tepat satu benar, pilih-banyak ≥2 benar.";
      return;
    }
    error = "";
    busy = "q-edit";
    try {
      const payload = buildQuestionPayload(editQ, 0);
      delete (payload as Record<string, unknown>).position;
      if (editQ.qtype !== "multiple_choice" && editQ.qtype !== "multi_select") {
        delete (payload as Record<string, unknown>).options;
      }
      await api.patch(`/questions/${editingQ}`, payload);
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

  async function moveQ(index: number, delta: number) {
    const next = index + delta;
    if (next < 0 || next >= questions.length) return;
    const ordered = questions.map((q) => q.id);
    [ordered[index], ordered[next]] = [ordered[next], ordered[index]];
    error = "";
    message = "";
    busy = "q-reorder";
    try {
      await api.post(`/exams/${examId}/questions/reorder`, { question_ids: ordered });
      await loadQuestions();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah urutan soal";
    } finally {
      busy = "";
    }
  }

  /** Approve or reject an AI-generated question awaiting review. */
  async function reviewQ(q: Question, status: "approved" | "rejected") {
    error = "";
    message = "";
    busy = `qr-${q.id}`;
    try {
      await api.patch(`/questions/${q.id}`, { review_status: status });
      message = status === "approved" ? "Soal disetujui." : "Soal ditolak.";
      await loadQuestions();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal meninjau soal";
    } finally {
      busy = "";
    }
  }

  const REVIEW_LABEL: Record<string, string> = {
    pending: "Menunggu tinjauan",
    approved: "Disetujui",
    rejected: "Ditolak",
  };

  const QTYPE_BADGES: Record<string, string> = {
    essay: "Esai",
    multiple_choice: "PG",
    true_false: "B/S",
    multi_select: "Pilih Banyak",
    numeric: "Angka",
    fill_blank: "Isian",
    matching: "Cocokkan",
    ordering: "Urutkan",
  };

  // --- question bank import ---
  interface BankQuestion {
    id: string;
    prompt: string;
    qtype: string;
  }
  let bank: BankQuestion[] = [];
  let bankOpen = false;
  let bankLoading = false;
  let bankQuery = "";
  let bankQtype = "";

  async function loadBank() {
    bankLoading = true;
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (bankQtype) params.set("qtype", bankQtype);
      if (bankQuery.trim()) params.set("query", bankQuery.trim());
      bank = await api.get<BankQuestion[]>(`/questions/bank?${params.toString()}`);
    } catch {
      bank = [];
    } finally {
      bankLoading = false;
    }
  }

  async function toggleBank() {
    bankOpen = !bankOpen;
    if (bankOpen && bank.length === 0) {
      await loadBank();
    }
  }

  $: filteredBank = bank.filter((bq) => {
    const matchQuery =
      !bankQuery.trim() || bq.prompt.toLowerCase().includes(bankQuery.trim().toLowerCase());
    const matchType = !bankQtype || bq.qtype === bankQtype;
    return matchQuery && matchType;
  });

  async function importFromBank(questionId: string) {
    error = "";
    message = "";
    busy = `bank-${questionId}`;
    try {
      await api.post(`/exams/${examId}/questions/attach`, { question_id: questionId });
      message = "Soal diimpor dari bank.";
      await loadQuestions();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengimpor soal";
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
        <label class="block">
          <span class="mono-label">Maks. percobaan (0 = tak terbatas)</span>
          <input
            class="input mt-1"
            type="number"
            min="0"
            max="100"
            bind:value={form.max_attempts}
          />
        </label>
      </div>
      <div class="mt-3 flex flex-wrap items-center gap-4">
        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" bind:checked={form.shuffle_questions} />
          <span>Acak urutan soal per siswa</span>
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" bind:checked={form.shuffle_options} />
          <span>Acak urutan opsi jawaban</span>
        </label>
      </div>
      <div class="mt-3 grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="mono-label">Toleransi keterlambatan (detik)</span>
          <input
            class="input mt-1"
            type="number"
            min="0"
            max="3600"
            bind:value={form.grace_seconds}
          />
        </label>
        <label class="block">
          <span class="mono-label">Penalti telat (bp, mis. 2000 = -20%)</span>
          <input
            class="input mt-1"
            type="number"
            min="0"
            max="10000"
            bind:value={form.late_penalty_bp}
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
                {#if editQ.qtype === "multiple_choice" || editQ.qtype === "multi_select"}
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
                {:else if editQ.qtype === "true_false"}
                  <select class="input mt-2 !w-auto !py-1" bind:value={editQ.tf}>
                    <option value="true">Benar</option>
                    <option value="false">Salah</option>
                  </select>
                {:else if editQ.qtype === "numeric"}
                  <div class="mt-2 flex items-center gap-2">
                    <span class="mono-label">Nilai</span>
                    <input
                      class="input !w-28 !py-1"
                      type="number"
                      step="any"
                      bind:value={editQ.numericValue}
                    />
                    <span class="mono-label">Toleransi</span>
                    <input
                      class="input !w-24 !py-1"
                      type="number"
                      min="0"
                      step="any"
                      bind:value={editQ.numericTolerance}
                    />
                  </div>
                {:else if editQ.qtype === "fill_blank"}
                  <input
                    class="input mt-2"
                    placeholder="Jawaban diterima, pisahkan dengan koma"
                    bind:value={editQ.fillAnswers}
                  />
                {:else if editQ.qtype === "ordering"}
                  <textarea
                    class="input mt-2 min-h-[80px]"
                    placeholder="Item dalam urutan benar, satu per baris"
                    bind:value={editQ.orderItems}
                  ></textarea>
                {:else if editQ.qtype === "matching"}
                  <textarea
                    class="input mt-2 min-h-[80px]"
                    placeholder="Pasangan kunci=nilai, satu per baris"
                    bind:value={editQ.matchPairs}
                  ></textarea>
                {:else}
                  <textarea
                    class="input mt-2 min-h-[60px]"
                    placeholder="Kunci jawaban"
                    bind:value={editQ.correct_answer}
                  ></textarea>
                {/if}
                <div class="mt-2 flex items-center gap-2">
                  <span class="mono-label">Bobot (%)</span>
                  <input
                    class="input !w-24 !py-1 text-sm"
                    type="number"
                    min="0"
                    max="100"
                    bind:value={editQ.weight}
                  />
                </div>
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
                  <span class="badge badge-indigo">{QTYPE_BADGES[q.qtype] ?? q.qtype}</span>
                  {#if q.review_status && q.review_status !== "approved"}
                    <span
                      class="badge"
                      class:badge-amber={q.review_status === "pending"}
                      class:badge-magenta={q.review_status === "rejected"}
                    >
                      {REVIEW_LABEL[q.review_status] ?? q.review_status}
                    </span>
                  {/if}
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
                  {#if questions.length > 1}
                    <button
                      class="btn-icon"
                      disabled={i === 0 || busy === "q-reorder"}
                      on:click={() => moveQ(i, -1)}
                      title="Pindah ke atas"
                      aria-label="Pindah ke atas"><Icon name="arrow-up" size="11px" /></button
                    >
                    <button
                      class="btn-icon"
                      disabled={i === questions.length - 1 || busy === "q-reorder"}
                      on:click={() => moveQ(i, 1)}
                      title="Pindah ke bawah"
                      aria-label="Pindah ke bawah"><Icon name="arrow-down" size="11px" /></button
                    >
                  {/if}
                  {#if q.review_status === "pending"}
                    <button
                      class="btn-icon !text-secondary hover:!border-secondary"
                      on:click={() => reviewQ(q, "approved")}
                      disabled={busy === `qr-${q.id}`}
                      title="Setujui soal"
                      aria-label="Setujui soal"><Icon name="circle-check" size="11px" /></button
                    >
                    <button
                      class="btn-icon !text-tertiary hover:!border-tertiary"
                      on:click={() => reviewQ(q, "rejected")}
                      disabled={busy === `qr-${q.id}`}
                      title="Tolak soal"
                      aria-label="Tolak soal"><Icon name="circle-xmark" size="11px" /></button
                    >
                  {/if}
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

        <div class="mt-3 border-t pt-3">
          <button class="btn-ghost !py-1 text-xs" on:click={toggleBank}>
            <Icon name="box-archive" size="11px" />
            {bankOpen ? "Tutup bank soal" : "Impor dari bank soal"}
          </button>
          {#if bankOpen}
            <div class="mt-2 space-y-2">
              <div class="flex flex-wrap items-center gap-2">
                <input
                  class="input !py-1 text-xs flex-1 min-w-[140px]"
                  placeholder="Cari dalam bank soal..."
                  bind:value={bankQuery}
                />
                <select class="input !w-auto !py-1 text-xs" bind:value={bankQtype}>
                  <option value="">Semua tipe</option>
                  <option value="essay">Esai</option>
                  <option value="multiple_choice">Pilihan ganda</option>
                  <option value="true_false">Benar/Salah</option>
                  <option value="multi_select">Pilih banyak</option>
                  <option value="numeric">Angka</option>
                  <option value="fill_blank">Isian singkat</option>
                  <option value="matching">Mencocokkan</option>
                  <option value="ordering">Mengurutkan</option>
                </select>
              </div>

              {#if bankLoading}
                <div class="skeleton h-8"></div>
              {:else if filteredBank.length === 0}
                <p class="text-xs muted">
                  {bank.length === 0
                    ? "Bank soal kosong."
                    : "Tidak ada soal yang cocok dengan filter."}
                </p>
              {:else}
                <ul class="max-h-52 space-y-1 overflow-y-auto">
                  {#each filteredBank as bq}
                    {@const isAlreadyAttached = questions.some((q) => q.prompt === bq.prompt)}
                    <li
                      class="flex items-center justify-between gap-2 text-sm rounded p-1 hover:bg-surface-elevated/40"
                    >
                      <div class="flex items-center gap-1.5 min-w-0 flex-1">
                        <span class="badge badge-indigo text-[10px] shrink-0">
                          {QTYPE_BADGES[bq.qtype] ?? bq.qtype}
                        </span>
                        <span class="truncate text-xs">{bq.prompt}</span>
                      </div>
                      <button
                        class="btn-ghost !py-0.5 text-xs shrink-0"
                        on:click={() => importFromBank(bq.id)}
                        disabled={busy === `bank-${bq.id}` || isAlreadyAttached}
                        title={isAlreadyAttached ? "Soal sudah ada pada ujian ini" : "Impor soal"}
                      >
                        {busy === `bank-${bq.id}` ? "…" : isAlreadyAttached ? "Ada" : "Impor"}
                      </button>
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
          {/if}
        </div>

        <div class="mt-3 space-y-2 border-t pt-3">
          <div class="flex items-center gap-2">
            <span class="mono-label">Tipe soal</span>
            <select class="input !w-auto !py-1" bind:value={newQ.qtype}>
              <option value="essay">Esai (dinilai AI)</option>
              <option value="multiple_choice">Pilihan ganda</option>
              <option value="true_false">Benar/Salah</option>
              <option value="multi_select">Pilih banyak</option>
              <option value="numeric">Angka (toleransi)</option>
              <option value="fill_blank">Isian singkat</option>
              <option value="matching">Mencocokkan</option>
              <option value="ordering">Mengurutkan</option>
            </select>
          </div>
          <input class="input" placeholder="Pertanyaan baru" bind:value={newQ.prompt} />
          {#if newQ.qtype === "multiple_choice" || newQ.qtype === "multi_select"}
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
          {:else if newQ.qtype === "true_false"}
            <select class="input !w-auto !py-1" bind:value={newQ.tf}>
              <option value="true">Benar</option>
              <option value="false">Salah</option>
            </select>
          {:else if newQ.qtype === "numeric"}
            <div class="flex items-center gap-2">
              <span class="mono-label">Nilai</span>
              <input
                class="input !w-28 !py-1"
                type="number"
                step="any"
                bind:value={newQ.numericValue}
              />
              <span class="mono-label">Toleransi</span>
              <input
                class="input !w-24 !py-1"
                type="number"
                min="0"
                step="any"
                bind:value={newQ.numericTolerance}
              />
            </div>
          {:else if newQ.qtype === "fill_blank"}
            <input
              class="input"
              placeholder="Jawaban diterima, pisahkan dengan koma"
              bind:value={newQ.fillAnswers}
            />
          {:else if newQ.qtype === "ordering"}
            <textarea
              class="input min-h-[80px]"
              placeholder="Item dalam urutan benar, satu per baris"
              bind:value={newQ.orderItems}
            ></textarea>
          {:else if newQ.qtype === "matching"}
            <textarea
              class="input min-h-[80px]"
              placeholder="Pasangan kunci=nilai, satu per baris"
              bind:value={newQ.matchPairs}
            ></textarea>
          {:else}
            <textarea
              class="input min-h-[70px]"
              placeholder="Kunci jawaban / acuan"
              bind:value={newQ.correct_answer}
            ></textarea>
          {/if}
          <div class="flex items-center gap-2">
            <span class="mono-label">Bobot (%)</span>
            <input
              class="input !w-24 !py-1 text-sm"
              type="number"
              min="0"
              max="100"
              bind:value={newQ.weight}
            />
          </div>
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
