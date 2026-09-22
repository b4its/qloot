<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { SubmissionRow, TeacherAnalytics } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let rows: SubmissionRow[] = [];
  let analytics: TeacherAnalytics | null = null;
  let loading = true;
  let error = "";
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    error = "";
    try {
      const offset = (page - 1) * PAGE;
      rows = await api.get<SubmissionRow[]>(`/teacher/submissions?limit=${PAGE}&offset=${offset}`);
      // Fewer than a full page means this is the last page.
      hasMore = rows.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pengumpulan";
    } finally {
      loading = false;
    }
  }

  async function loadAnalytics() {
    try {
      analytics = await api.get<TeacherAnalytics>("/teacher/analytics");
    } catch {
      analytics = null;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1) return;
    if (delta > 0 && !hasMore) return;
    page = next;
    load();
  }

  onMount(() => {
    load();
    loadAnalytics();
  });
</script>

<svelte:head><title>Pengumpulan — QLoot Guru</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panel Guru · Jawaban</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Pengumpulan</h1>
      <p class="mt-1 text-sm muted">
        Jawaban siswa terbaru dari ujianmu, lengkap dengan feedback AI.
      </p>
    </div>
    <a href="/teacher" class="btn-ghost">← Panel Guru</a>
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

  {#if loading}
    <p class="mt-6 muted">Memuat …</p>
  {:else if !rows.length}
    <div class="card mt-4 text-center"><p class="muted">Belum ada pengumpulan.</p></div>
  {:else}
    <div class="card mt-4 overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">Ujian</th><th>Siswa</th><th>Tipe</th><th>Soal</th><th>Jawaban</th><th
              >Benar?</th
            ><th class="text-right">Skor</th><th>Umpan balik</th></tr
          >
        </thead>
        <tbody>
          {#each rows as r}
            <tr class="border-t align-top">
              <td class="py-2">{r.exam_title}</td>
              <td class="py-2">
                {#if r.student_name}
                  {r.student_name}
                {:else}
                  <span class="font-mono text-xs">{r.student_id.slice(0, 8)}…</span>
                {/if}
              </td>
              <td>
                <span class="badge badge-indigo"
                  >{r.qtype === "multiple_choice" ? "PG" : "Esai"}</span
                >
              </td>
              <td class="max-w-[220px]">{r.prompt}</td>
              <td class="max-w-[260px] text-xs muted">
                {#if r.qtype === "multiple_choice"}
                  {#if r.answer_text}
                    <span class="mono">{r.answer_text}.</span>
                    {r.answer_display ?? ""}
                  {:else}
                    <span>tidak dijawab</span>
                  {/if}
                {:else}
                  {r.answer_text}
                {/if}
              </td>
              <td>
                {#if r.qtype === "multiple_choice"}
                  <span
                    class="badge"
                    class:badge-mint={r.is_correct === true}
                    class:badge-magenta={r.is_correct === false}
                    class:badge-neutral={r.is_correct === null || r.is_correct === undefined}
                  >
                    {r.is_correct === true ? "Benar" : r.is_correct === false ? "Salah" : "—"}
                  </span>
                {:else}
                  <span class="text-xs muted">—</span>
                {/if}
              </td>
              <td class="text-right font-mono">{bpToPercent(r.score_bp)}</td>
              <td class="max-w-[220px] text-xs muted">{r.feedback}</td>
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
