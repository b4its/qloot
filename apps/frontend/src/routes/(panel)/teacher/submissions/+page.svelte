<script lang="ts">
  import { onMount } from "svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { SubmissionRow, TeacherAnalytics, Exam } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import Dialog from "$lib/components/Dialog.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let rows: SubmissionRow[] = [];
  let exams: Exam[] = [];
  let analytics: TeacherAnalytics | null = null;
  let loading = true;
  let error = "";
  let page = 1;
  let hasMore = false;

  let searchQuery = "";
  let selectedExamId = "";
  let statusFilter: "all" | "correct" | "incorrect" | "ungraded" = "all";
  let inspectingRow: SubmissionRow | null = null;

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

  async function load() {
    loading = true;
    error = "";
    try {
      const offset = (page - 1) * PAGE;
      const params = new URLSearchParams({
        limit: String(PAGE),
        offset: String(offset),
      });
      if (selectedExamId) params.set("exam_id", selectedExamId);
      if (searchQuery.trim()) params.set("q", searchQuery.trim());
      // Filter server-side so the tabs, counts, and pagination stay consistent
      // across pages (a client-side filter would only see the current page).
      if (statusFilter !== "all") params.set("status", statusFilter);

      rows = await api.get<SubmissionRow[]>(`/teacher/submissions?${params.toString()}`);
      hasMore = rows.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pengumpulan";
    } finally {
      loading = false;
    }
  }

  async function loadExams() {
    try {
      exams = await api.get<Exam[]>("/exams?limit=200");
    } catch {
      exams = [];
    }
  }

  async function loadAnalytics() {
    try {
      analytics = await api.get<TeacherAnalytics>("/teacher/analytics");
    } catch {
      analytics = null;
    }
  }

  function handleSearch() {
    page = 1;
    load();
  }

  function setStatus(s: typeof statusFilter) {
    if (statusFilter === s) return;
    statusFilter = s;
    page = 1;
    load();
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1) return;
    if (delta > 0 && !hasMore) return;
    page = next;
    load();
  }

  // The server already filtered by status; keep this alias so the table and CSV
  // export continue to reference a single list.
  $: filteredRows = rows;

  function exportSubmissionsCsv() {
    if (!filteredRows.length) return;
    const headers = [
      "Ujian",
      "Siswa",
      "Tipe Soal",
      "Soal",
      "Jawaban Siswa",
      "Kunci / Pilihan Benar",
      "Status",
      "Skor (%)",
      "Umpan Balik AI",
    ];
    const lines = [headers.join(",")];
    for (const r of filteredRows) {
      const statusStr =
        r.is_correct === true ? "Benar" : r.is_correct === false ? "Salah" : "Belum Dinilai";
      const scoreStr = r.score_bp != null ? bpToPercent(r.score_bp) : "-";
      const answerStr = (r.answer_display ?? r.answer_text ?? "").replace(/"/g, '""');
      const correctStr = (r.correct_display ?? r.correct_answer ?? "").replace(/"/g, '""');
      const feedbackStr = (r.feedback ?? "").replace(/"/g, '""');
      const promptStr = (r.prompt ?? "").replace(/"/g, '""');
      const studentStr = (r.student_name ?? r.student_id ?? "").replace(/"/g, '""');
      const examStr = (r.exam_title ?? "").replace(/"/g, '""');
      lines.push(
        `"${examStr}","${studentStr}","${r.qtype}","${promptStr}","${answerStr}","${correctStr}","${statusStr}","${scoreStr}","${feedbackStr}"`,
      );
    }
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rekap-pengumpulan-guru-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  onMount(() => {
    load();
    loadExams();
    loadAnalytics();
  });
</script>

<svelte:head><title>Pengumpulan — QLoot Guru</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panel Guru · Jawaban</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Pengumpulan Siswa</h1>
      <p class="mt-1 text-sm muted">
        Jawaban siswa terbaru dari ujian Anda, lengkap dengan penilaian otomatis dan feedback AI.
      </p>
    </div>
    <div class="flex items-center gap-2">
      <button
        type="button"
        class="btn-secondary !py-1.5 text-xs flex items-center gap-1.5"
        on:click={exportSubmissionsCsv}
        disabled={!filteredRows.length}
      >
        <Icon name="file-arrow-down" size="12px" />
        <span>Ekspor CSV ({filteredRows.length})</span>
      </button>
      <a href="/teacher" class="btn-ghost !py-1.5 text-xs">← Panel Guru</a>
    </div>
  </div>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  {#if analytics}
    <div class="mt-6 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
      <div class="card">
        <div class="mono-label">Ujian</div>
        <div class="mt-1 font-display text-2xl font-bold">{analytics.exams}</div>
      </div>
      <div class="card">
        <div class="mono-label">Ternilai</div>
        <div class="mt-1 font-display text-2xl font-bold">{analytics.graded_attempts}</div>
      </div>
      <div class="card">
        <div class="mono-label">Rata-rata skor</div>
        <div class="mt-1 font-display text-2xl font-bold">
          {bpToPercent(analytics.average_score_bp)}
        </div>
      </div>
      <div class="card">
        <div class="mono-label">Tingkat kelulusan</div>
        <div class="mt-1 font-display text-2xl font-bold">
          {bpToPercent(analytics.pass_rate_bp)}
        </div>
      </div>
      <div class="card">
        <div class="mono-label">Pemenang</div>
        <div class="mt-1 font-display text-2xl font-bold">{analytics.winners}</div>
      </div>
      <div class="card">
        <div class="mono-label">OPT diberikan</div>
        <div class="mt-1 font-display text-2xl font-bold text-highlight">
          {analytics.opc_awarded}
        </div>
      </div>
    </div>
  {/if}

  <!-- Search & Filter Controls -->
  <div class="mt-6 flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2 flex-1">
      <div class="relative w-full sm:w-64">
        <input
          type="text"
          class="input text-xs !py-1.5 w-full"
          placeholder="Cari siswa, ujian, atau soal..."
          bind:value={searchQuery}
          on:keydown={(e) => e.key === "Enter" && handleSearch()}
        />
        {#if searchQuery}
          <button
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
            on:click={() => {
              searchQuery = "";
              handleSearch();
            }}
          >
            ✕
          </button>
        {/if}
      </div>

      {#if exams.length > 0}
        <select
          class="input text-xs !py-1.5 !w-auto"
          bind:value={selectedExamId}
          on:change={handleSearch}
        >
          <option value="">Semua Ujian</option>
          {#each exams as e}
            <option value={e.id}>{e.title}</option>
          {/each}
        </select>
      {/if}
    </div>

    <!-- Status filter tabs -->
    <div
      class="flex items-center gap-1 rounded-sm border p-1 surface text-xs"
      role="group"
      aria-label="Filter status jawaban"
    >
      <button
        type="button"
        class="px-2.5 py-1 rounded-xs font-medium transition-colors"
        class:bg-primary={statusFilter === "all"}
        class:text-[#05060A]={statusFilter === "all"}
        class:muted={statusFilter !== "all"}
        aria-pressed={statusFilter === "all"}
        on:click={() => setStatus("all")}
      >
        Semua
      </button>
      <button
        type="button"
        class="px-2.5 py-1 rounded-xs font-medium transition-colors"
        class:bg-primary={statusFilter === "correct"}
        class:text-[#05060A]={statusFilter === "correct"}
        class:muted={statusFilter !== "correct"}
        aria-pressed={statusFilter === "correct"}
        on:click={() => setStatus("correct")}
      >
        Benar
      </button>
      <button
        type="button"
        class="px-2.5 py-1 rounded-xs font-medium transition-colors"
        class:bg-primary={statusFilter === "incorrect"}
        class:text-[#05060A]={statusFilter === "incorrect"}
        class:muted={statusFilter !== "incorrect"}
        aria-pressed={statusFilter === "incorrect"}
        on:click={() => setStatus("incorrect")}
      >
        Salah
      </button>
      <button
        type="button"
        class="px-2.5 py-1 rounded-xs font-medium transition-colors"
        class:bg-primary={statusFilter === "ungraded"}
        class:text-[#05060A]={statusFilter === "ungraded"}
        class:muted={statusFilter !== "ungraded"}
        aria-pressed={statusFilter === "ungraded"}
        on:click={() => setStatus("ungraded")}
      >
        Esai/Manual
      </button>
    </div>
  </div>

  {#if loading}
    <div class="mt-4"><Skeleton rows={4} /></div>
  {:else if !filteredRows.length}
    <div class="card mt-4 text-center py-12">
      <p class="muted">
        {searchQuery || selectedExamId || statusFilter !== "all"
          ? "Tidak ada pengumpulan yang sesuai dengan filter atau kata kunci."
          : "Belum ada pengumpulan jawaban dari siswa."}
      </p>
    </div>
  {:else}
    <div class="card mt-4 overflow-x-auto !p-0">
      <table class="w-full text-sm">
        <caption class="sr-only">Pengumpulan jawaban siswa</caption>
        <thead class="text-left muted surface border-b text-xs font-mono">
          <tr>
            <th class="py-2.5 px-4" scope="col">Ujian</th>
            <th class="py-2.5 px-4" scope="col">Siswa</th>
            <th class="py-2.5 px-4" scope="col">Tipe</th>
            <th class="py-2.5 px-4" scope="col">Soal</th>
            <th class="py-2.5 px-4" scope="col">Jawaban Siswa</th>
            <th class="py-2.5 px-4" scope="col">Status</th>
            <th class="py-2.5 px-4 text-right" scope="col">Skor</th>
            <th class="py-2.5 px-4" scope="col">Umpan Balik AI</th>
            <th class="py-2.5 px-4 text-center" scope="col">Aksi</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border/60">
          {#each filteredRows as r}
            <tr class="align-top hover:bg-surface/60 transition-colors">
              <td class="py-3 px-4 font-medium max-w-[180px] truncate" title={r.exam_title}>
                {r.exam_title}
              </td>
              <td class="py-3 px-4 max-w-[140px] truncate">
                {#if r.student_name}
                  <span class="font-medium">{r.student_name}</span>
                {:else}
                  <span class="font-mono text-xs muted">{r.student_id.slice(0, 8)}…</span>
                {/if}
              </td>
              <td class="py-3 px-4">
                <span
                  class="badge border text-[10px]"
                  class:badge-indigo={r.qtype === "multiple_choice"}
                  class:badge-purple={r.qtype !== "multiple_choice"}
                >
                  {QTYPE_LABELS[r.qtype] ?? r.qtype}
                </span>
              </td>
              <td class="py-3 px-4 max-w-[200px] truncate text-xs" title={r.prompt}>
                {r.prompt}
              </td>
              <td class="py-3 px-4 max-w-[220px] truncate text-xs muted">
                {#if r.qtype === "multiple_choice"}
                  {#if r.answer_text}
                    <span class="font-mono text-primary font-bold">{r.answer_text}.</span>
                    {r.answer_display ?? ""}
                  {:else}
                    <span class="italic">tidak dijawab</span>
                  {/if}
                {:else}
                  {r.answer_text ?? "—"}
                {/if}
              </td>
              <td class="py-3 px-4">
                <span
                  class="badge text-[10px]"
                  class:badge-mint={r.is_correct === true}
                  class:badge-magenta={r.is_correct === false}
                  class:badge-neutral={r.is_correct === null || r.is_correct === undefined}
                >
                  {r.is_correct === true
                    ? "Benar"
                    : r.is_correct === false
                      ? "Salah"
                      : "Belum Dinilai"}
                </span>
              </td>
              <td class="py-3 px-4 text-right font-mono text-xs">
                {#if r.score_bp != null}
                  <span
                    class={r.is_correct === true
                      ? "text-mint font-bold"
                      : r.is_correct === false
                        ? "text-magenta"
                        : "text-primary"}
                  >
                    {bpToPercent(r.score_bp)}
                  </span>
                {:else}
                  <span class="muted">—</span>
                {/if}
              </td>
              <td class="py-3 px-4 max-w-[200px] truncate text-xs muted" title={r.feedback ?? ""}>
                {r.feedback ?? "—"}
              </td>
              <td class="py-3 px-4 text-center">
                <button
                  type="button"
                  class="btn-ghost !py-0.5 !px-2 text-xs"
                  on:click={() => (inspectingRow = r)}
                >
                  Detail
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <Pagination
      {page}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="pengumpulan"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {/if}
</div>

{#if inspectingRow}
  <Dialog
    title="Detail Pengumpulan Siswa"
    description={`Siswa: ${inspectingRow.student_name ?? inspectingRow.student_id}`}
    size="max-w-2xl"
    close={() => (inspectingRow = null)}
  >
    <div class="space-y-3">
      <div class="rounded-sm border p-3 surface space-y-1.5 text-xs">
        <div class="flex items-center justify-between">
          <span class="badge badge-indigo text-[10px]"
            >{QTYPE_LABELS[inspectingRow.qtype] ?? inspectingRow.qtype}</span
          >
          <span class="font-mono text-muted">ID Soal: {inspectingRow.question_id.slice(0, 8)}…</span
          >
        </div>
        <p class="font-medium text-sm text-foreground leading-relaxed pt-1">
          {inspectingRow.prompt}
        </p>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div class="rounded-sm border p-3 surface">
          <span class="mono-label text-[10px]">Jawaban Siswa</span>
          <p class="mt-1 font-medium text-foreground whitespace-pre-wrap">
            {#if inspectingRow.answer_text}
              {#if inspectingRow.qtype === "multiple_choice"}
                <span class="font-mono text-primary font-bold">{inspectingRow.answer_text}.</span>
                {inspectingRow.answer_display ?? ""}
              {:else}
                {inspectingRow.answer_text}
              {/if}
            {:else}
              <span class="muted italic">Tidak dijawab</span>
            {/if}
          </p>
        </div>

        <div class="rounded-sm border p-3 surface">
          <span class="mono-label text-[10px]">Kunci / Jawaban Benar</span>
          <p class="mt-1 font-medium text-foreground">
            {#if inspectingRow.correct_answer}
              <span class="font-mono text-mint font-bold">{inspectingRow.correct_answer}.</span>
              {inspectingRow.correct_display ?? ""}
            {:else}
              <span class="muted">—</span>
            {/if}
          </p>
        </div>
      </div>

      <div class="flex items-center justify-between rounded-sm border p-3 surface text-xs">
        <div class="flex items-center gap-2">
          <span class="mono-label">Status:</span>
          <span
            class="badge"
            class:badge-mint={inspectingRow.is_correct === true}
            class:badge-magenta={inspectingRow.is_correct === false}
            class:badge-neutral={inspectingRow.is_correct == null}
          >
            {inspectingRow.is_correct === true
              ? "Benar"
              : inspectingRow.is_correct === false
                ? "Salah"
                : "Belum Dinilai"}
          </span>
        </div>
        <div>
          <span class="mono-label">Skor:</span>
          <span class="font-mono font-bold text-sm ml-1 text-primary"
            >{bpToPercent(inspectingRow.score_bp)}</span
          >
        </div>
      </div>

      {#if inspectingRow.feedback}
        <div class="rounded-sm border border-secondary/30 bg-secondary/10 p-3 text-xs space-y-1">
          <div class="flex items-center gap-1.5 font-bold text-secondary">
            <Icon name="robot" size="12px" />
            <span>Umpan Balik AI</span>
          </div>
          <p class="text-muted leading-relaxed whitespace-pre-wrap">{inspectingRow.feedback}</p>
        </div>
      {/if}
    </div>

    <svelte:fragment slot="footer">
      <div class="flex items-center justify-end">
        <button class="btn-ghost text-xs" on:click={() => (inspectingRow = null)}>Tutup</button>
      </div>
    </svelte:fragment>
  </Dialog>
{/if}
