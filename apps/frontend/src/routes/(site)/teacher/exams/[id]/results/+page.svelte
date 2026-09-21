<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam, Attempt } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import { bpToPercent, statusLabel } from "$lib/utils/format";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const examId = $page.params.id;
  const PAGE = 50;

  let exam: Exam | null = null;
  let results: Attempt[] = [];
  let loading = true;
  let error = "";

  onMount(async () => {
    try {
      [exam, results] = await Promise.all([
        api.get<Exam>(`/exams/${examId}`),
        api.get<Attempt[]>(`/exams/${examId}/results?limit=${PAGE}`),
      ]);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat hasil";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>Hasil Ujian — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Ujian"
    title="Hasil peserta"
    subtitle={exam?.title ?? "Hasil ujian"}
    backHref={`/teacher/exams/${examId}`}
    backLabel="Kelola ujian"
  />

  <PageAlerts {error} />

  {#if loading}
    <div class="mt-6 space-y-2">
      {#each Array(4) as _}<div class="skeleton h-10"></div>{/each}
    </div>
  {:else if results.length === 0}
    <div class="card mt-6 grid place-items-center py-12 text-center">
      <Icon name="inbox" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada pengumpulan</p>
      <p class="text-sm muted">Hasil akan muncul setelah siswa mengerjakan ujian.</p>
    </div>
  {:else}
    <div class="card mt-6 overflow-x-auto !p-0">
      <table class="w-full text-sm">
        <thead class="mono-label border-b text-left">
          <tr>
            <th class="px-5 py-3">Peserta</th>
            <th class="px-5 py-3">Percobaan</th>
            <th class="px-5 py-3">Status</th>
            <th class="px-5 py-3 text-right">Skor</th>
          </tr>
        </thead>
        <tbody>
          {#each results as a}
            <tr class="border-b last:border-0">
              <td class="px-5 py-3 font-mono text-xs">{a.user_id.slice(0, 8)}…</td>
              <td class="px-5 py-3">#{a.attempt_number}</td>
              <td class="px-5 py-3">{statusLabel(a.status)}</td>
              <td class="px-5 py-3 text-right">
                {a.score_bp !== null && a.score_bp !== undefined ? bpToPercent(a.score_bp) : "—"}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
