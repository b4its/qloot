<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError, API_BASE } from "$lib/api/client";
  import type {
    AcademicDashboard,
    Personality,
    UserBadge,
    Course,
    Badge,
    BadgeProgress,
    NotificationPage,
    Progress,
    Attempt,
    Exam,
    GradeRow,
    GamificationProfile,
    Quest,
    Reward,
    Task,
  } from "$lib/types";
  import { buildMissions, primaryMission } from "$lib/utils/mission";
  import { onboardingSteps, onboardingComplete } from "$lib/utils/mission";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import ProgressRing from "$lib/components/ProgressRing.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import OptChip from "$lib/components/OptChip.svelte";
  import CertificateBadge from "$lib/components/CertificateBadge.svelte";

  let acad: AcademicDashboard | null = null;
  let personality: Personality | null = null;
  let badges: UserBadge[] = [];
  let badgeCatalog: Badge[] = [];
  let subjects: Course[] = [];
  let wallet: { available: number; token_id: number } | null = null;
  let gamification: GamificationProfile | null = null;
  let badgeProgress: BadgeProgress[] = [];
  let unread = 0;
  let loading = true;
  let error = "";
  let unavailableSections: string[] = [];

  // Mission control data (reuses already-fetched courses/progress/exams/attempts).
  let exams: Exam[] = [];
  let attempts: Attempt[] = [];
  let quests: Quest[] = [];
  let tasks: Task[] = [];
  let taskCompletions: { task_id: string }[] = [];
  let rewards: Reward[] = [];
  let learningProgress: Progress[] = [];

  // Grade entry (feeds the academic dashboard + recommender).
  const SUBJECTS = [
    "Matematika",
    "Fisika",
    "Kimia",
    "Biologi",
    "B. Indonesia",
    "B. Inggris",
    "Ekonomi",
    "Sejarah",
    "Sosiologi",
    "Geografi",
  ];
  let grades: GradeRow[] = [];
  let gradeSubject = SUBJECTS[0];
  let gradeValue = 80;
  let gradeTerm = "2025/2026-genap";
  let gradeBusy = false;
  let gradeMsg = "";

  $: canManageGrades = hasRole($auth.user, "teacher");

  $: averageGradeScore = grades.length
    ? Math.round(grades.reduce((sum, g) => sum + g.grade, 0) / grades.length)
    : 0;

  $: bestSubject = grades.length
    ? [...grades].sort((a, b) => b.grade - a.grade)[0]
    : null;

  function gradeTier(score: number) {
    if (score >= 85) {
      return {
        tier: "Predikat A",
        badgeClass: "badge badge-mint",
        colorClass: "text-emerald-400",
        barClass: "bg-emerald-400",
        statusText: "Sangat Baik (Tuntas)",
      };
    }
    if (score >= 75) {
      return {
        tier: "Predikat B",
        badgeClass: "badge badge-indigo",
        colorClass: "text-cyan-400",
        barClass: "bg-cyan-400",
        statusText: "Baik (Memenuhi KKM)",
      };
    }
    if (score >= 60) {
      return {
        tier: "Predikat C",
        badgeClass: "badge badge-amber",
        colorClass: "text-amber-400",
        barClass: "bg-amber-400",
        statusText: "Cukup",
      };
    }
    return {
      tier: "Predikat D",
      badgeClass: "badge badge-magenta",
      colorClass: "text-rose-400",
      barClass: "bg-rose-400",
      statusText: "Perlu Bimbingan",
    };
  }

  async function reloadAcademic() {
    // Re-fetch after a grade write. If the refresh fails the write still
    // succeeded, so note it rather than silently showing stale academic data.
    try {
      acad = await api.get<AcademicDashboard>("/career/dashboard");
    } catch {
      gradeMsg = "Nilai tersimpan, tetapi ringkasan akademik belum dapat diperbarui.";
    }
  }

  async function addGrade() {
    if (!canManageGrades) {
      gradeMsg = "Hanya guru dan admin yang diizinkan menginput nilai.";
      return;
    }
    gradeMsg = "";
    const value = Number(gradeValue);
    if (!Number.isFinite(value) || value < 0 || value > 100) {
      gradeMsg = "Nilai harus antara 0 dan 100.";
      return;
    }
    gradeBusy = true;
    try {
      await api.post("/career/grades", {
        subject: gradeSubject,
        grade: value,
        term: gradeTerm,
      });
      grades = await api.get<GradeRow[]>("/career/grades");
      await reloadAcademic();
      gradeMsg = `${gradeSubject}: ${value}`;
    } catch (e) {
      gradeMsg = e instanceof ApiError ? e.message : "Gagal menyimpan nilai";
    } finally {
      gradeBusy = false;
    }
  }

  async function editGrade(g: GradeRow) {
    if (!canManageGrades || !g.id) return;
    // Inline editing replaces the old native prompt(): the row turns into an
    // input that saves on confirm, keeping the interaction themed and a11y-safe.
    editingGradeId = g.id;
    gradeEditValue = g.grade;
    gradeMsg = "";
  }
  let editingGradeId: string | null = null;
  let gradeEditValue = 0;

  async function saveGradeEdit(g: GradeRow) {
    if (!canManageGrades || !g.id || editingGradeId !== g.id) return;
    const value = Number(gradeEditValue);
    if (!Number.isFinite(value) || value < 0 || value > 100) {
      gradeMsg = "Nilai harus antara 0 dan 100.";
      return;
    }
    gradeMsg = "";
    gradeBusy = true;
    try {
      await api.put(`/career/grades/${g.id}`, { grade: value });
      grades = await api.get<GradeRow[]>("/career/grades");
      await reloadAcademic();
      gradeMsg = `${g.subject} diperbarui menjadi ${value}.`;
      editingGradeId = null;
    } catch (e) {
      gradeMsg = e instanceof ApiError ? e.message : "Gagal memperbarui nilai";
    } finally {
      gradeBusy = false;
    }
  }

  function cancelGradeEdit() {
    editingGradeId = null;
  }

  async function deleteGrade(g: GradeRow) {
    if (!canManageGrades || !g.id) return;
    deletingGrade = g;
  }

  async function confirmDeleteGrade() {
    const g = deletingGrade;
    if (!canManageGrades || !g?.id) return;
    deletingGrade = null;
    gradeMsg = "";
    gradeBusy = true;
    try {
      await api.delete(`/career/grades/${g.id}`);
      grades = await api.get<GradeRow[]>("/career/grades");
      await reloadAcademic();
      gradeMsg = `${g.subject} dihapus.`;
    } catch (e) {
      gradeMsg = e instanceof ApiError ? e.message : "Gagal menghapus nilai";
    } finally {
      gradeBusy = false;
    }
  }
  let deletingGrade: GradeRow | null = null;

  // Real activity heatmap: bucket actual events (lesson completions, exam
  // submissions, badge awards) into days. No fabricated data: an account with
  // no events simply shows an empty grid.
  const weeks = 18;
  const dayMs = 24 * 60 * 60 * 1000;
  let activityCounts: Record<string, number> = {};

  function dayKey(d: Date): string {
    return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  }

  function buildActivity(
    prog: Progress[],
    attempts: Attempt[],
    userBadges: UserBadge[],
  ): Record<string, number> {
    const counts: Record<string, number> = {};
    const add = (iso?: string | null) => {
      if (!iso) return;
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return;
      const k = dayKey(d);
      counts[k] = (counts[k] ?? 0) + 1;
    };
    for (const p of prog) if (p.completed) add(p.completed_at);
    for (const a of attempts) add(a.submitted_at);
    for (const b of userBadges) add(b.awarded_at);
    return counts;
  }

  // Cells are laid out oldest → newest, aligned so the last cell is today.
  $: gridStart = (() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return new Date(today.getTime() - (weeks * 7 - 1) * dayMs);
  })();

  function cellDate(i: number): Date {
    return new Date(gridStart.getTime() + i * dayMs);
  }

  function cellLevel(i: number): number {
    const inFuture = cellDate(i).getTime() > Date.now();
    if (inFuture) return -1; // rendered as a dimmed placeholder
    const n = activityCounts[dayKey(cellDate(i))] ?? 0;
    if (n === 0) return 0;
    if (n === 1) return 1;
    if (n <= 3) return 2;
    return 3;
  }

  $: totalActivity = Object.values(activityCounts).reduce((a, b) => a + b, 0);
  const intensity = ["bg-ink/5", "bg-secondary/30", "bg-secondary/55", "bg-secondary/80"];

  onMount(() => {
    (async () => {
      const safe = async <T,>(request: Promise<T>, fallback: T, label: string): Promise<T> => {
        try {
          return await request;
        } catch {
          unavailableSections = [...unavailableSections, label];
          return fallback;
        }
      };

      try {
        const [a, p, b, w, s, g, bc, prog, atts, gam, bp, np, ex, qu, tk, tc, rw] =
          await Promise.all([
            safe(api.get<AcademicDashboard | null>("/career/dashboard"), null, "performa akademik"),
            // A failed personality fetch must not look like "never taken the test",
            // so route it through the shared unavailable-sections tracker.
            safe(api.get<Personality | null>("/career/personality"), null, "profil kepribadian"),
            safe(api.get<UserBadge[]>("/me/badges"), [], "badge"),
            safe(
              api.get<{ available: number; token_id: number } | null>("/wallet"),
              null,
              "saldo OPT",
            ),
            safe(api.get<Course[]>("/courses"), [], "pelajaran"),
            safe(api.get<GradeRow[]>("/career/grades"), [], "nilai"),
            safe(api.get<Badge[]>("/badges"), [], "katalog badge"),
            safe(api.get<Progress[]>("/me/learning-progress"), [], "progres belajar"),
            safe(api.get<Attempt[]>("/attempts"), [], "riwayat ujian"),
            safe(api.get<GamificationProfile | null>("/gamification/me"), null, "gamifikasi"),
            safe(api.get<BadgeProgress[]>("/badges/progress"), [], "progres badge"),
            safe(
              api.get<NotificationPage | null>("/notifications/page?limit=1"),
              null,
              "notifikasi",
            ),
            safe(api.get<Exam[]>("/exams"), [], "daftar ujian"),
            safe(api.get<Quest[]>("/quests"), [], "quest"),
            safe(api.get<Task[]>("/tasks"), [], "tugas"),
            safe(api.get<{ task_id: string }[]>("/tasks/me/completions"), [], "status tugas"),
            safe(api.get<Reward[]>("/wallet/rewards?limit=20"), [], "hadiah"),
          ]);
        acad = a;
        personality = p;
        badges = b;
        wallet = w;
        subjects = s;
        grades = g;
        badgeCatalog = bc;
        gamification = gam;
        activityCounts = buildActivity(prog, atts, b);
        learningProgress = prog;
        badgeProgress = bp;
        unread = np?.unread ?? 0;
        exams = ex;
        attempts = atts;
        quests = qu;
        tasks = tk;
        taskCompletions = tc;
        rewards = rw;
      } catch (e) {
        error = e instanceof ApiError ? e.message : "";
      } finally {
        loading = false;
      }
    })().catch((e) => {
      error = e instanceof ApiError ? e.message : "";
      loading = false;
    });
  });

  function pct(p: BadgeProgress): number {
    if (p.target <= 0) return 0;
    return Math.min(100, Math.max(0, Math.round((p.current / p.target) * 100)));
  }

  // The badges closest to unlocking (locked, with the least remaining): the
  // most motivating next goals to surface on the home screen.
  $: nearestBadges = badgeProgress
    .filter((p) => !p.unlocked && p.target > 0)
    .sort((a, b) => b.current / b.target - a.current / a.target)
    .slice(0, 3);

  $: user = $auth.user;

  // Unified next-action feed derived from already-fetched data.
  $: missions = buildMissions({
    courses: subjects,
    progress: learningProgress,
    exams,
    attempts,
    quests,
    tasks,
    completions: taskCompletions,
    rewards,
  });
  $: topMission = primaryMission(missions);
  $: followUpMissions = missions.filter((m) => m.id !== topMission?.id).slice(0, 4);

  // Onboarding checklist: only meaningful while the student is still ramping up.
  $: onboarding = onboardingSteps({
    hasClass: !!user?.class_code,
    hasCourse: subjects.length > 0,
    hasCompletedLesson: learningProgress.some((p) => p.completed),
    hasEarnedReward: rewards.length > 0 || (wallet?.available ?? 0) > 0,
  });
  $: onboardingDone = onboardingComplete(onboarding);
</script>

<svelte:head><title>Dashboard | QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-10 sm:px-6">
  <p class="mono-label">Semester Genap 2025/2026</p>
  <h1 class="mt-1 font-display text-3xl font-bold">
    Halo, {user?.full_name?.split(" ")[0] ?? "Pelajar"}
  </h1>
  <p class="mt-1 muted">Lanjutkan belajarmu dan jaga momentum.</p>

  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">{error}</p>
  {/if}
  {#if unavailableSections.length}
    <div class="alert-warning mt-4 flex items-start gap-3" role="status">
      <Icon name="triangle-exclamation" class="mt-0.5" />
      <p>
        Sebagian data belum dapat dimuat: {unavailableSections.join(", ")}. Angka pada bagian
        tersebut mungkin belum mencerminkan kondisi terbaru.
      </p>
    </div>
  {/if}

  {#if loading}
    <div class="mt-6 grid gap-4 sm:grid-cols-3">
      {#each Array(3) as _}<div class="skeleton h-32"></div>{/each}
    </div>
  {:else}
    <!-- Mission control: the single most valuable next action -->
    <section class="mt-6" aria-labelledby="mission-heading" data-role="mission-feed">
      <div class="flex items-center justify-between">
        <h2 id="mission-heading" class="font-display font-bold">Misi berikutnya</h2>
        {#if missions.length > 1}
          <span class="mono-label">{missions.length} tindakan</span>
        {/if}
      </div>

      {#if topMission}
        <a
          href={topMission.href}
          class="card lift mt-3 flex flex-wrap items-center justify-between gap-4 {topMission.tone ===
          'urgent'
            ? 'border-danger/50'
            : ''}"
          data-role="mission-primary"
        >
          <div class="flex items-center gap-4">
            <span
              class="tile h-12 w-12 {topMission.tone === 'urgent'
                ? '!bg-danger/10 !text-danger'
                : ''}"
            >
              <Icon
                name={topMission.tone === "urgent"
                  ? "triangle-exclamation"
                  : topMission.kind === "settlement"
                    ? "coins"
                    : "circle-play"}
                size="20px"
              />
            </span>
            <div>
              <p class="mono-label text-[10px]">
                {topMission.tone === "urgent" ? "Perlu segera" : "Lanjutkan di sini"}
              </p>
              <p class="font-display text-lg font-bold">{topMission.title}</p>
              <p class="text-xs muted">{topMission.description}</p>
            </div>
          </div>
          <span class="btn-primary" data-role="mission-primary-cta">
            Buka <Icon name="arrow-right" size="11px" />
          </span>
        </a>
      {:else if !onboardingDone}
        <!-- New-student onboarding: guide to the first verified reward (W2) -->
        <div class="card mt-3" data-role="onboarding-checklist">
          <p class="font-semibold">Mulai dari sini</p>
          <p class="mt-1 text-xs muted">
            Tiga langkah untuk memulai perjalanan belajarmu dan meraih hadiah pertama.
          </p>
          <ol class="mt-3 space-y-2">
            {#each onboarding as step (step.key)}
              <li>
                <a
                  href={step.href}
                  class="flex items-center gap-3 rounded-sm border p-3 text-sm transition-colors hover:border-primary/50 {step.done
                    ? 'opacity-70'
                    : ''}"
                  data-role="onboarding-step"
                  data-done={step.done}
                >
                  <Icon
                    name={step.done ? "circle-check" : "circle"}
                    size="16px"
                    class={step.done ? "text-mint flex-none" : "muted flex-none"}
                  />
                  <span class="min-w-0">
                    <span class="block font-medium {step.done ? 'line-through' : ''}"
                      >{step.title}</span
                    >
                    <span class="block text-xs muted">{step.description}</span>
                  </span>
                </a>
              </li>
            {/each}
          </ol>
        </div>
      {:else}
        <div class="card mt-3 flex items-center gap-3">
          <Icon name="circle-check" size="18px" class="text-mint" />
          <p class="text-sm muted">
            Semua misi selesai. Jelajahi <a href="/learning" class="text-primary">pelajaran</a> atau
            <a href="/community" class="text-primary">komunitas</a> untuk hal baru.
          </p>
        </div>
      {/if}

      {#if followUpMissions.length}
        <ul class="mt-3 grid gap-2 sm:grid-cols-2" aria-label="Tindakan lain">
          {#each followUpMissions as m (m.id)}
            <li>
              <a
                href={m.href}
                class="card flex items-center justify-between gap-3 !p-3 hover:border-primary/50"
                data-role="mission-item"
              >
                <span class="min-w-0">
                  <span class="block truncate text-sm font-semibold">{m.title}</span>
                  <span class="block truncate text-xs muted">{m.description}</span>
                </span>
                <span
                  class="badge {m.tone === 'urgent'
                    ? 'badge-magenta'
                    : m.tone === 'reward'
                      ? 'badge-amber'
                      : 'badge-neutral'} flex-none"
                >
                  {m.kind}
                </span>
              </a>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <!-- top stats -->
    <div class="mt-6 grid gap-4 sm:grid-cols-3">
      <div class="card flex items-center gap-4">
        <ProgressRing value={acad?.average ?? 0} size={92} stroke={9} label="Rata-rata skor" />
        <div>
          <p class="mono-label">Rata-rata Skor</p>
          <p class="text-sm muted">
            Terkuat: <span class="text-ink">{acad?.strong_subject ?? "-"}</span>
          </p>
          <p class="text-sm muted">
            Perhatian: <span class="text-ink">{acad?.weak_subject ?? "-"}</span>
          </p>
        </div>
      </div>
      <div class="card">
        <p class="mono-label">OPT tersedia</p>
        <p class="mt-2 font-display text-3xl font-bold text-highlight">
          <StatCounter value={wallet?.available ?? 0} />
        </p>
        <p class="text-xs muted">token id {wallet?.token_id ?? 0}</p>
      </div>
      <div class="card">
        <p class="mono-label">Badge diraih</p>
        <p class="mt-2 font-display text-3xl font-bold"><StatCounter value={badges.length} /></p>
        <p class="text-xs muted">dari {badgeCatalog.length || "-"} tersedia</p>
      </div>
    </div>

    <!-- next goals: unread inbox + nearest badges -->
    {#if unread > 0 || nearestBadges.length}
      <div class="mt-4 grid gap-4 lg:grid-cols-2" data-role="next-goals">
        <div class="card">
          <div class="flex items-center justify-between">
            <h2 class="font-display font-bold">Kotak masuk</h2>
            <a href="/notifications" class="text-xs text-primary"
              >Buka <Icon name="arrow-right" size="10px" /></a
            >
          </div>
          {#if unread > 0}
            <div class="mt-3 flex items-center gap-3">
              <span class="tile-neutral h-10 w-10">
                <Icon name="bell" size="15px" class="text-highlight" />
              </span>
              <div>
                <p class="font-display text-2xl font-bold" data-role="unread-count">{unread}</p>
                <p class="text-xs muted">notifikasi belum dibaca</p>
              </div>
            </div>
          {:else}
            <div class="mt-3 flex items-center gap-3">
              <span class="tile-neutral h-10 w-10">
                <Icon name="bell-slash" size="15px" class="muted" />
              </span>
              <p class="text-sm muted">Semua notifikasi sudah dibaca. Kerja bagus!</p>
            </div>
          {/if}
        </div>

        <div class="card">
          <div class="flex items-center justify-between">
            <h2 class="font-display font-bold">Badge terdekat</h2>
            <a href="/badges" class="text-xs text-primary"
              >Semua badge <Icon name="arrow-right" size="10px" /></a
            >
          </div>
          {#if nearestBadges.length}
            <ul class="mt-3 space-y-3">
              {#each nearestBadges as p (p.badge.code)}
                <li>
                  <div class="flex items-center justify-between text-xs">
                    <span class="inline-flex items-center gap-2">
                      <Icon name="medal" size="11px" class="text-secondary" />
                      <span class="font-medium">{p.badge.name}</span>
                    </span>
                    <span class="mono muted">{p.current}/{p.target}</span>
                  </div>
                  <div
                    class="mt-1.5 h-1.5 w-full overflow-hidden rounded-full"
                    style="background: rgb(var(--line))"
                    role="progressbar"
                    aria-valuenow={p.current}
                    aria-valuemin={0}
                    aria-valuemax={p.target}
                    aria-label={`Progres ${p.badge.name}`}
                  >
                    <div
                      class="h-full rounded-full bg-secondary transition-all"
                      style={`width: ${pct(p)}%`}
                    ></div>
                  </div>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="mt-3 text-sm muted">Semua badge sudah kamu raih. Luar biasa!</p>
          {/if}
        </div>
      </div>
    {/if}

    <!-- grades editor -->
    <div class="card mt-4 overflow-hidden border border-slate-700/60 bg-slate-900/60 p-4 sm:p-5">
      <!-- Header section -->
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-center gap-2.5">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon name="book-open" size="16px" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h2 class="font-display font-bold text-base sm:text-lg text-slate-100">Rapor & Nilai Akademik</h2>
              <span class="badge badge-mint gap-1 text-2xs py-0.5 px-2">
                <Icon name="check" size="9px" /> Terverifikasi
              </span>
            </div>
            <p class="mt-0.5 text-xs muted">
              {#if canManageGrades}
                Kelola nilai capaian rapor siswa untuk dashboard analitik dan panduan SNBP/SNBT.
              {:else}
                Nilai capaian rapor resmi yang terdaftar dan diverifikasi oleh guru untuk analisis rekomendasi jurusan.
              {/if}
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2.5 self-end sm:self-auto">
          {#if grades.length}
            <a
              href={`${API_BASE}/api/v1/career/grades/export.csv`}
              class="btn-ghost !py-1 text-xs"
              download
            >
              <Icon name="download" size="11px" /> Ekspor CSV
            </a>
          {/if}
          <a href="/career/roadmap" class="btn-ghost !py-1 text-xs text-primary hover:text-primary-focus">
            Analisis jurusan <Icon name="arrow-right" size="10px" />
          </a>
        </div>
      </div>

      <!-- Ringkasan Nilai Cepat (Jika ada nilai) -->
      {#if grades.length}
        <div class="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
            <span class="text-2xs font-semibold uppercase tracking-wider text-slate-400">Rata-rata Nilai</span>
            <div class="mt-1 flex items-baseline gap-2">
              <span class="font-display text-2xl font-black text-slate-100">{averageGradeScore}</span>
              <span class="text-xs text-slate-400">/ 100</span>
              <span class={`ml-auto ${gradeTier(averageGradeScore).badgeClass} text-2xs`}>
                {gradeTier(averageGradeScore).tier}
              </span>
            </div>
          </div>
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
            <span class="text-2xs font-semibold uppercase tracking-wider text-slate-400">Mapel Unggulan</span>
            <div class="mt-1 flex items-baseline justify-between">
              <span class="truncate font-display text-sm font-bold text-emerald-400">
                {bestSubject?.subject ?? "-"}
              </span>
              {#if bestSubject}
                <span class="font-mono text-sm font-extrabold text-slate-200">{bestSubject.grade}</span>
              {/if}
            </div>
          </div>
          <div class="col-span-2 rounded-xl border border-slate-800 bg-slate-950/60 p-3 sm:col-span-1">
            <span class="text-2xs font-semibold uppercase tracking-wider text-slate-400">Total Mata Pelajaran</span>
            <div class="mt-1 flex items-baseline justify-between">
              <span class="font-display text-2xl font-black text-slate-100">{grades.length}</span>
              <span class="badge badge-neutral text-2xs">Semester Aktif</span>
            </div>
          </div>
        </div>
      {/if}

      <!-- Form Input Nilai Khusus Guru & Admin -->
      {#if canManageGrades}
        <div class="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-3.5">
          <div class="flex items-center gap-1.5 text-xs font-semibold text-primary">
            <Icon name="plus" size="11px" /> Input Nilai Akademik Siswa (Guru & Admin)
          </div>
          <div class="mt-2.5 grid gap-2 sm:grid-cols-[1fr_100px_150px_auto]">
            <select class="input" bind:value={gradeSubject} aria-label="Mata pelajaran">
              {#each SUBJECTS as s}<option value={s}>{s}</option>{/each}
            </select>
            <input
              class="input"
              type="number"
              min="0"
              max="100"
              bind:value={gradeValue}
              aria-label="Nilai (0-100)"
            />
            <input
              class="input"
              placeholder="2025/2026-genap"
              bind:value={gradeTerm}
              aria-label="Semester"
            />
            <button class="btn-primary" on:click={addGrade} disabled={gradeBusy}>
              {#if gradeBusy}<Icon name="spinner" spin size="12px" />{:else}<Icon
                  name="plus"
                  size="12px"
                />{/if}
              Simpan
            </button>
          </div>
        </div>
      {/if}

      {#if gradeMsg}
        <p class="mt-2 text-xs muted" role="status" aria-live="polite">{gradeMsg}</p>
      {/if}

      <!-- Daftar Kartu Nilai Rapor Modern -->
      {#if grades.length}
        <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {#each grades as g}
            {@const tier = gradeTier(g.grade)}
            <div class="group relative flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-950/40 p-3.5 transition-all hover:border-slate-700 hover:bg-slate-950/80">
              {#if g.id && editingGradeId === g.id && canManageGrades}
                <!-- Mode Edit Inline Khusus Guru / Admin -->
                <div class="flex flex-col gap-2">
                  <div class="flex items-center justify-between">
                    <span class="font-display text-sm font-bold text-slate-100">{g.subject}</span>
                    <span class="badge badge-neutral text-2xs">{g.term}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <input
                      class="input !w-20 !px-2 !py-1 text-sm font-bold"
                      type="number"
                      min="0"
                      max="100"
                      bind:value={gradeEditValue}
                      aria-label={`Nilai baru ${g.subject}`}
                    />
                    <button
                      class="btn-primary !px-2.5 !py-1 text-xs"
                      on:click={() => saveGradeEdit(g)}
                      disabled={gradeBusy}
                      aria-label={`Simpan nilai ${g.subject}`}
                    >
                      <Icon name={gradeBusy ? "spinner" : "check"} spin={gradeBusy} size="11px" />
                    </button>
                    <button
                      class="btn-ghost !px-2.5 !py-1 text-xs"
                      on:click={cancelGradeEdit}
                      disabled={gradeBusy}
                      aria-label={`Batal ubah nilai ${g.subject}`}
                    >
                      <Icon name="xmark" size="11px" />
                    </button>
                  </div>
                </div>
              {:else}
                <div>
                  <div class="flex items-start justify-between gap-2">
                    <div>
                      <h3 class="font-display text-sm font-bold text-slate-100">{g.subject}</h3>
                      <span class="text-2xs text-slate-400 font-mono">{g.term}</span>
                    </div>
                    <span class={`${tier.badgeClass} text-2xs font-bold py-0.5 px-2`}>
                      {tier.tier}
                    </span>
                  </div>

                  <div class="mt-3 flex items-baseline justify-between">
                    <div class="flex items-baseline gap-1">
                      <span class={`font-display text-2xl font-black ${tier.colorClass}`}>
                        {g.grade}
                      </span>
                      <span class="text-xs text-slate-400">/ 100</span>
                    </div>
                    <span class="text-2xs text-slate-400 font-medium">
                      {tier.statusText}
                    </span>
                  </div>

                  <!-- Visual Progress Bar -->
                  <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800/80">
                    <div
                      class={`h-full rounded-full transition-all duration-500 ${tier.barClass}`}
                      style={`width: ${Math.min(100, Math.max(0, g.grade))}%`}
                    ></div>
                  </div>
                </div>

                <!-- Kontrol Guru/Admin: Ubah & Hapus -->
                {#if canManageGrades && g.id}
                  <div class="mt-3.5 flex items-center justify-end gap-1.5 border-t border-slate-800/80 pt-2.5">
                    <button
                      class="btn-ghost !px-2 !py-1 text-2xs text-slate-400 hover:text-primary"
                      on:click={() => editGrade(g)}
                      disabled={gradeBusy}
                      aria-label={`Ubah nilai ${g.subject}`}
                    >
                      <Icon name="pen" size="10px" /> Ubah
                    </button>
                    <button
                      class="btn-ghost !px-2 !py-1 text-2xs text-slate-400 hover:text-rose-400"
                      on:click={() => deleteGrade(g)}
                      disabled={gradeBusy}
                      aria-label={`Hapus nilai ${g.subject}`}
                    >
                      <Icon name="xmark" size="10px" /> Hapus
                    </button>
                  </div>
                {/if}
              {/if}
            </div>
          {/each}
        </div>
      {:else}
        <div class="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-950/30 p-8 text-center">
          <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-800/50 text-slate-400">
            <Icon name="book-open" size="24px" />
          </div>
          <h3 class="mt-3 font-display text-sm font-bold text-slate-200">Belum Ada Nilai Rapor</h3>
          <p class="mx-auto mt-1 max-w-md text-xs text-slate-400">
            {#if canManageGrades}
              Gunakan formulir di atas untuk menginput nilai akademik siswa pertama kali.
            {:else}
              Nilai akademik akan diinput dan diverifikasi oleh guru mata pelajaran atau wali kelas Anda.
            {/if}
          </p>
        </div>
      {/if}

      {#if acad?.insights?.length}
        <div class="mt-4 border-t pt-3">
          <p class="mono-label">Wawasan akademik</p>
          <ul class="mt-2 space-y-2 text-sm">
            {#each acad.insights as ins}
              <li class="flex items-start gap-2">
                <Icon name="lightbulb" size="12px" class="mt-0.5 text-primary flex-none" />
                <span>
                  <span class="font-medium">{ins.title}</span>
                  <span class="muted">: {ins.detail}</span>
                </span>
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if acad?.radar?.length}
        <div class="mt-4 border-t pt-3">
          <p class="mono-label">Profil minat</p>
          <div class="mt-2 space-y-2">
            {#each acad.radar as dim}
              <div>
                <div class="flex items-center justify-between text-xs">
                  <span>{dim.dimension}</span>
                  <span class="mono muted">{dim.value}</span>
                </div>
                <div
                  class="mt-1 h-1.5 w-full overflow-hidden rounded-sm bg-ink/10"
                  role="progressbar"
                  aria-label={`Nilai minat ${dim.dimension}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.max(0, Math.min(100, dim.value))}
                >
                  <div
                    class="h-full rounded-sm bg-primary"
                    style={`width:${Math.max(0, Math.min(100, dim.value))}%`}
                  ></div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>

    <!-- streak + current path -->
    <div class="mt-4 grid gap-4 lg:grid-cols-3">
      <div class="card lg:col-span-2">
        <div class="flex items-center justify-between">
          <h2 class="font-display font-bold">Aktivitas belajar</h2>
          <span class="mono-label">{weeks} minggu terakhir</span>
        </div>
        {#if gamification && gamification.current_streak > 0}
          <p class="mt-1 text-xs muted">
            <Icon name="fire" size="10px" class="text-tertiary" />
            Streak {gamification.current_streak} hari berturut-turut
            {#if gamification.best_streak > gamification.current_streak}
              · terbaik {gamification.best_streak} hari
            {/if}
          </p>
        {/if}
        {#if totalActivity === 0}
          <p class="mt-4 text-sm muted">
            Belum ada aktivitas tercatat. Selesaikan materi, kumpulkan ujian, atau raih badge untuk
            mengisi kalender ini.
          </p>
        {:else}
          <div class="mt-4 flex flex-wrap gap-1">
            {#each Array(weeks * 7) as _, i}
              {@const lvl = cellLevel(i)}
              <span
                class="h-3 w-3 rounded-[3px] {lvl < 0 ? 'bg-transparent' : intensity[lvl]}"
                title={lvl < 0
                  ? "Belum berjalan"
                  : `${activityCounts[dayKey(cellDate(i))] ?? 0} aktivitas · ${cellDate(i).toLocaleDateString("id-ID", { day: "2-digit", month: "short" })}`}
              ></span>
            {/each}
          </div>
          <div class="mt-3 flex items-center justify-between text-xs muted">
            <span>{totalActivity} aktivitas · {Object.keys(activityCounts).length} hari aktif</span>
            <span class="flex items-center gap-2">
              <span>Sedikit</span>
              {#each intensity as c}<span class="h-3 w-3 rounded-[3px] {c}"></span>{/each}
              <span>Banyak</span>
            </span>
          </div>
        {/if}
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <p class="mono-label">Kelas saya</p>
          <OptChip compact={true} />
        </div>
        <div class="mt-3 flex items-center gap-3">
          <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
            <Icon name="chalkboard-user" size="18px" />
          </span>
          <div>
            <p class="font-display text-lg font-bold">
              {user?.class_code ?? "Belum ada kelas"}{user?.class_type
                ? ` · ${user.class_type}`
                : ""}
            </p>
            <p class="text-xs muted">{subjects.length} pelajaran tersedia</p>
          </div>
        </div>
        <ul class="mt-3 space-y-1.5 text-sm">
          {#each subjects.slice(0, 3) as s}
            <li>
              <a
                href={`/courses/${s.id}`}
                class="flex items-center justify-between rounded-sm px-2 py-1.5 hover:bg-ink/5"
              >
                <span class="inline-flex items-center gap-2"
                  ><Icon name="book-open-reader" size="11px" class="text-primary" />
                  {s.title}</span
                >
                <Icon name="chevron-right" size="9px" class="muted" />
              </a>
            </li>
          {/each}
          {#if subjects.length === 0}<li class="text-xs muted">
              Guru belum menambahkan pelajaran.
            </li>{/if}
        </ul>
        {#if subjects.length > 0}
          <a href="/learning" class="btn-secondary mt-4 w-full">Buka pelajaran saya</a>
        {/if}
      </div>
    </div>

    <!-- personality + certificates -->
    <div class="mt-4 grid gap-4 lg:grid-cols-3">
      <div class="card">
        <h2 class="font-display font-bold">Profil kepribadian</h2>
        {#if personality}
          <div class="mt-3 space-y-2">
            {#each [{ l: "Keterbukaan", v: personality.openness }, { l: "Kehati-hatian", v: personality.conscientiousness }, { l: "Ekstroversi", v: personality.extraversion }, { l: "Keramahan", v: personality.agreeableness }] as t}
              <div>
                <div class="flex justify-between text-xs">
                  <span class="muted">{t.l}</span><span class="mono">{t.v}</span>
                </div>
                <div
                  class="track mt-1 h-1"
                  role="progressbar"
                  aria-label={`Nilai kepribadian ${t.l}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={t.v}
                >
                  <span style={`width:${t.v}%`}></span>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <p class="mt-2 text-sm muted">
            Belum ada hasil. Ikuti tes kepribadian untuk profil personal.
          </p>
          <a href="/career/personality" class="btn-secondary mt-3 w-full">Ikuti tes</a>
        {/if}
      </div>

      <div class="lg:col-span-2">
        <div class="flex items-center justify-between">
          <h2 class="font-display font-bold">Sertifikat & badge</h2>
          <a href="/certificates" class="text-xs text-primary"
            >Lihat semua <Icon name="arrow-right" size="10px" /></a
          >
        </div>
        {#if badges.length}
          <div class="mt-3 grid gap-4 sm:grid-cols-2">
            {#each badges.slice(0, 2) as b}
              <CertificateBadge
                title={b.badge.name}
                subtitle={b.badge.description ?? ""}
                edition={`+${b.badge.points} POIN`}
                icon="medal"
                compact
              />
            {/each}
          </div>
        {:else}
          <div class="card mt-3 grid place-items-center py-10 text-center">
            <Icon name="certificate" size="26px" class="muted" />
            <p class="mt-2 text-sm muted">
              Selesaikan pelajaran untuk meraih sertifikat pertamamu.
            </p>
            <a href="/courses" class="btn-secondary mt-3">Jelajahi pelajaran</a>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

{#if deletingGrade}
  <ConfirmDialog
    title="Hapus Nilai"
    description={`Nilai ${deletingGrade.subject} (${deletingGrade.term}) akan dihapus dari rapor.`}
    hint="Nilai ini juga memengaruhi tren dan rekomendasi jurusanmu."
    confirmLabel="Ya, Hapus"
    busy={gradeBusy}
    onConfirm={confirmDeleteGrade}
    close={() => (deletingGrade = null)}
  />
{/if}
