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
    GradeRow,
    GamificationProfile,
  } from "$lib/types";
  import { auth } from "$lib/stores/auth";
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
    if (!g.id) return;
    // Inline editing replaces the old native prompt(): the row turns into an
    // input that saves on confirm, keeping the interaction themed and a11y-safe.
    editingGradeId = g.id;
    gradeEditValue = g.grade;
    gradeMsg = "";
  }
  let editingGradeId: string | null = null;
  let gradeEditValue = 0;

  async function saveGradeEdit(g: GradeRow) {
    if (!g.id || editingGradeId !== g.id) return;
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
    if (!g.id) return;
    deletingGrade = g;
  }

  async function confirmDeleteGrade() {
    const g = deletingGrade;
    if (!g?.id) return;
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
  // submissions, badge awards) into days. No fabricated data — an account with
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

  onMount(async () => {
    const safe = async <T,>(request: Promise<T>, fallback: T, label: string): Promise<T> => {
      try {
        return await request;
      } catch {
        unavailableSections = [...unavailableSections, label];
        return fallback;
      }
    };

    try {
      const [a, p, b, w, s, g, bc, prog, atts, gam, bp, np] = await Promise.all([
        safe(api.get<AcademicDashboard | null>("/career/dashboard"), null, "performa akademik"),
        // A failed personality fetch must not look like "never taken the test",
        // so route it through the shared unavailable-sections tracker.
        safe(api.get<Personality | null>("/career/personality"), null, "profil kepribadian"),
        safe(api.get<UserBadge[]>("/me/badges"), [], "badge"),
        safe(api.get<{ available: number; token_id: number } | null>("/wallet"), null, "saldo OPT"),
        safe(api.get<Course[]>("/courses"), [], "pelajaran"),
        safe(api.get<GradeRow[]>("/career/grades"), [], "nilai"),
        safe(api.get<Badge[]>("/badges"), [], "katalog badge"),
        safe(api.get<Progress[]>("/me/learning-progress"), [], "progres belajar"),
        safe(api.get<Attempt[]>("/attempts"), [], "riwayat ujian"),
        safe(api.get<GamificationProfile | null>("/gamification/me"), null, "gamifikasi"),
        safe(api.get<BadgeProgress[]>("/badges/progress"), [], "progres badge"),
        safe(api.get<NotificationPage | null>("/notifications/page?limit=1"), null, "notifikasi"),
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
      badgeProgress = bp;
      unread = np?.unread ?? 0;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "";
    } finally {
      loading = false;
    }
  });

  function pct(p: BadgeProgress): number {
    if (p.target <= 0) return 0;
    return Math.min(100, Math.max(0, Math.round((p.current / p.target) * 100)));
  }

  // The badges closest to unlocking (locked, with the least remaining) — the
  // most motivating next goals to surface on the home screen.
  $: nearestBadges = badgeProgress
    .filter((p) => !p.unlocked && p.target > 0)
    .sort((a, b) => b.current / b.target - a.current / a.target)
    .slice(0, 3);

  $: user = $auth.user;
</script>

<svelte:head><title>Dashboard — QLoot</title></svelte:head>

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
    <!-- top stats -->
    <div class="mt-6 grid gap-4 sm:grid-cols-3">
      <div class="card flex items-center gap-4">
        <ProgressRing value={acad?.average ?? 0} size={92} stroke={9} label="Rata-rata" />
        <div>
          <p class="mono-label">Performa</p>
          <p class="text-sm muted">
            Terkuat: <span class="text-ink">{acad?.strong_subject ?? "—"}</span>
          </p>
          <p class="text-sm muted">
            Perhatian: <span class="text-ink">{acad?.weak_subject ?? "—"}</span>
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
        <p class="text-xs muted">dari {badgeCatalog.length || "—"} tersedia</p>
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
    <div class="card mt-4">
      <div class="flex items-center justify-between">
        <h2 class="font-display font-bold">Nilai akademik</h2>
        <div class="flex items-center gap-3">
          {#if grades.length}
            <a
              href={`${API_BASE}/api/v1/career/grades/export.csv`}
              class="btn-ghost !py-1 text-xs"
              download
            >
              <Icon name="download" size="11px" /> Ekspor CSV
            </a>
          {/if}
          <a href="/career/roadmap" class="text-xs text-primary"
            >Analisis jurusan <Icon name="arrow-right" size="10px" /></a
          >
        </div>
      </div>
      <p class="mt-1 text-xs muted">
        Masukkan nilai rapor — dipakai untuk dashboard, tren, dan rekomendasi jurusan.
      </p>
      <div class="mt-3 grid gap-2 sm:grid-cols-[1fr_100px_150px_auto]">
        <select class="input" bind:value={gradeSubject} aria-label="Mata pelajaran">
          {#each SUBJECTS as s}<option value={s}>{s}</option>{/each}
        </select>
        <input
          class="input"
          type="number"
          min="0"
          max="100"
          bind:value={gradeValue}
          aria-label="Nilai (0–100)"
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
      {#if gradeMsg}
        <p class="mt-2 text-xs muted" role="status" aria-live="polite">{gradeMsg}</p>
      {/if}
      {#if grades.length}
        <div class="mt-3 flex flex-wrap gap-1.5">
          {#each grades as g}
            {#if g.id && editingGradeId === g.id}
              <span class="badge badge-indigo gap-1.5 py-1">
                {g.subject}
                <input
                  class="input !w-16 !px-1.5 !py-0.5 text-xs"
                  type="number"
                  min="0"
                  max="100"
                  bind:value={gradeEditValue}
                  aria-label={`Nilai baru ${g.subject}`}
                />
                <button
                  class="hover:text-primary"
                  on:click={() => saveGradeEdit(g)}
                  disabled={gradeBusy}
                  aria-label={`Simpan nilai ${g.subject}`}
                >
                  <Icon name={gradeBusy ? "spinner" : "check"} spin={gradeBusy} size="10px" />
                </button>
                <button
                  class="hover:text-tertiary"
                  on:click={cancelGradeEdit}
                  disabled={gradeBusy}
                  aria-label={`Batal ubah nilai ${g.subject}`}
                >
                  <Icon name="xmark" size="10px" />
                </button>
              </span>
            {:else}
              <span class="badge badge-neutral">
                {g.subject} · {g.grade}
                <span class="muted">({g.term})</span>
                {#if g.id}
                  <button
                    class="ml-1 hover:text-primary"
                    on:click={() => editGrade(g)}
                    disabled={gradeBusy}
                    aria-label={`Ubah nilai ${g.subject}`}
                  >
                    <Icon name="pen" size="9px" />
                  </button>
                  <button
                    class="ml-1 hover:text-tertiary"
                    on:click={() => deleteGrade(g)}
                    disabled={gradeBusy}
                    aria-label={`Hapus nilai ${g.subject}`}
                  >
                    <Icon name="xmark" size="9px" />
                  </button>
                {/if}
              </span>
            {/if}
          {/each}
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
                  <span class="muted"> — {ins.detail}</span>
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
                <div class="mt-1 h-1.5 w-full overflow-hidden rounded-sm bg-ink/10">
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
                <div class="track mt-1 h-1">
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
            <p class="mt-2 text-sm muted">Selesaikan kursus untuk meraih sertifikat pertamamu.</p>
            <a href="/courses" class="btn-secondary mt-3">Jelajahi kursus</a>
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
