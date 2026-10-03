<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { auth, hasRole } from "$lib/stores/auth";
  import { api, ApiError } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";
  import type { TeacherAnalytics } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";
  import { teacherNav } from "$lib/data/role-nav";

  // Redirect once auth has resolved; a mount-only check missed the case where
  // auth was still loading, briefly exposing the panel to non-teachers.
  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let analytics: TeacherAnalytics | null = null;
  let error = "";
  let loading = true;

  // The hub shows every teacher section except the "Ringkasan" entry (this page).
  const links = teacherNav.filter((l) => l.href !== "/teacher");

  $: metrics = analytics
    ? [
        { label: "Ujian", value: analytics.exams },
        { label: "Dinilai", value: analytics.graded_attempts },
        { label: "Rata-rata", value: bpToPercent(analytics.average_score_bp) },
        { label: "Kelulusan", value: bpToPercent(analytics.pass_rate_bp), tone: "text-mint" },
        { label: "Quest", value: analytics.quests },
        { label: "OPT dibagi", value: analytics.opc_awarded, tone: "text-highlight" },
      ]
    : [];

  $: actionQueue = analytics?.actions ?? [];

  async function load() {
    loading = true;
    error = "";
    try {
      analytics = await api.get<TeacherAnalytics>("/teacher/analytics");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat analitik";
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Panel Guru | QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Panel Guru</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Kelola pembelajaran</h1>
  <p class="mt-2 muted">Buat materi, jalankan ujian, dan pantau kemajuan siswa.</p>

  {#if error}
    <div class="alert-error mt-4 flex flex-wrap items-center justify-between gap-3" role="alert">
      <span>{error}</span>
      <button class="btn-ghost !py-1 text-xs" on:click={load} disabled={loading}>
        <Icon name="rotate" size="11px" /> Coba lagi
      </button>
    </div>
  {/if}

  {#if loading}
    <div class="mt-6 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
      {#each Array(6) as _}<div class="skeleton h-24"></div>{/each}
    </div>
  {:else if analytics}
    <MetricStrip {metrics} columns={3} />

    <!-- Action queue: what needs the teacher's attention now -->
    <section class="mt-8" aria-labelledby="action-queue-heading">
      <div class="flex items-center justify-between">
        <h2 id="action-queue-heading" class="font-display font-bold">Perlu tindakan</h2>
        {#if actionQueue.length}
          <span class="mono-label">{actionQueue.length} antrean</span>
        {/if}
      </div>
      {#if actionQueue.length}
        <ul class="mt-3 grid gap-2 sm:grid-cols-2" data-role="teacher-action-queue">
          {#each actionQueue as a (a.kind)}
            <li>
              <a
                href={a.href}
                class="card flex items-center justify-between gap-3 !p-4 hover:border-primary/50"
              >
                <span class="flex items-center gap-3 min-w-0">
                  <span
                    class="tile h-10 w-10 flex-none {a.severity === 'urgent'
                      ? 'bg-danger/10 text-danger'
                      : a.severity === 'warning'
                        ? 'bg-amber/10 text-amber'
                        : 'bg-secondary/10 text-secondary'}"
                  >
                    <Icon
                      name={a.kind === "grading_failed"
                        ? "triangle-exclamation"
                        : a.kind === "consultation"
                          ? "comments"
                          : a.kind === "career_review"
                            ? "compass"
                            : "file-circle-question"}
                      size="16px"
                    />
                  </span>
                  <span class="min-w-0">
                    <span class="block text-sm font-semibold">{a.label}</span>
                    <span class="block text-xs muted">{a.count} item</span>
                  </span>
                </span>
                <span class="badge badge-neutral flex-none">{a.count}</span>
              </a>
            </li>
          {/each}
        </ul>
      {:else}
        <div class="card mt-3 flex items-center gap-3">
          <Icon name="circle-check" size="18px" class="text-mint" />
          <p class="text-sm muted">Tidak ada antrean mendesak. Semua tinjauan sudah tertangani.</p>
        </div>
      {/if}
    </section>

    <!-- Cohort mastery + transparent, non-punitive at-risk list (W6) -->
    {#if (analytics.mastery?.length ?? 0) > 0 || (analytics.at_risk?.length ?? 0) > 0}
      <section class="mt-8" aria-labelledby="cohort-heading">
        <h2 id="cohort-heading" class="font-display font-bold">Analitik kelas</h2>
        <div class="mt-3 grid gap-4 lg:grid-cols-2">
          <div class="card" data-role="cohort-mastery">
            <p class="mono-label text-[10px]">Penguasaan per ujian</p>
            {#if (analytics.mastery?.length ?? 0) > 0}
              <ul class="mt-3 divide-y text-sm">
                {#each analytics.mastery ?? [] as m (m.exam_id)}
                  <li class="flex items-center justify-between gap-3 py-2">
                    <span class="min-w-0">
                      <span class="block truncate font-medium">{m.exam_title}</span>
                      <span class="block text-xs muted">{m.attempts} percobaan dinilai</span>
                    </span>
                    <span class="flex-none text-right">
                      <span class="block font-mono text-sm">{bpToPercent(m.average_score_bp)}</span>
                      <span class="block text-xs muted">lulus {bpToPercent(m.pass_rate_bp)}</span>
                    </span>
                  </li>
                {/each}
              </ul>
            {:else}
              <p class="mt-2 text-sm muted">Belum ada percobaan dinilai.</p>
            {/if}
          </div>

          <div class="card" data-role="cohort-at-risk">
            <p class="mono-label text-[10px]">Perlu pendampingan</p>
            <p class="mt-1 text-xs muted">
              Siswa dengan skor terbaik di bawah ambang kelulusan. Bersifat mendukung, bukan hukuman
             : pertimbangkan materi tambahan atau konsultasi.
            </p>
            {#if (analytics.at_risk?.length ?? 0) > 0}
              <ul class="mt-3 divide-y text-sm">
                {#each analytics.at_risk ?? [] as s (s.student_id)}
                  <li class="flex items-center justify-between gap-3 py-2">
                    <span class="truncate">{s.student_name}</span>
                    <span class="flex-none font-mono text-xs muted">
                      {bpToPercent(s.best_score_bp)} / {bpToPercent(s.passing_score_bp)}
                    </span>
                  </li>
                {/each}
              </ul>
              <a href="/teacher/consultations" class="btn-secondary mt-3 !py-1.5 text-xs">
                <Icon name="comments" size="11px" /> Jadwalkan pendampingan
              </a>
            {:else}
              <p class="mt-2 text-sm muted">Semua siswa yang dinilai memenuhi ambang kelulusan.</p>
            {/if}
          </div>
        </div>
      </section>
    {/if}
  {/if}

  <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
    {#each links as l}
      <a href={l.href} class="card lift block">
        <span class="tile-cool h-11 w-11">
          <Icon name={l.icon} size="18px" />
        </span>
        <h2 class="mt-3 font-display text-lg font-bold">{l.label}</h2>
        <p class="mt-1 text-sm muted">{l.desc}</p>
      </a>
    {/each}
  </div>
</div>
