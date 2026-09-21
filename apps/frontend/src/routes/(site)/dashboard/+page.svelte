<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { AcademicDashboard, Personality, UserBadge, Course } from "$lib/types";
  import { auth } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import ProgressRing from "$lib/components/ProgressRing.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";
  import OpcChip from "$lib/components/OpcChip.svelte";
  import CertificateBadge from "$lib/components/CertificateBadge.svelte";

  let acad: AcademicDashboard | null = null;
  let personality: Personality | null = null;
  let badges: UserBadge[] = [];
  let subjects: Course[] = [];
  let wallet: { available: number; token_id: number } | null = null;
  let loading = true;
  let error = "";

  // Grade entry (feeds the academic dashboard + recommender).
  interface Grade {
    subject: string;
    grade: number;
    term: string;
  }
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
  let grades: Grade[] = [];
  let gradeSubject = SUBJECTS[0];
  let gradeValue = 80;
  let gradeTerm = "2025/2026-genap";
  let gradeBusy = false;
  let gradeMsg = "";

  async function reloadAcademic() {
    acad = await api.get<AcademicDashboard>("/career/dashboard").catch(() => acad);
  }

  async function addGrade() {
    gradeMsg = "";
    gradeBusy = true;
    try {
      await api.post("/career/grades", {
        subject: gradeSubject,
        grade: Number(gradeValue),
        term: gradeTerm,
      });
      grades = await api.get<Grade[]>("/career/grades");
      await reloadAcademic();
      gradeMsg = `${gradeSubject}: ${gradeValue}`;
    } catch (e) {
      gradeMsg = e instanceof ApiError ? e.message : "Gagal menyimpan nilai";
    } finally {
      gradeBusy = false;
    }
  }

  const sections = [
    { href: "/dashboard", label: "Beranda", icon: "gauge-high" },
    { href: "/learning", label: "Pelajaran Saya", icon: "book-open-reader" },
    { href: "/badges", label: "Sertifikat & Badge", icon: "certificate" },
    { href: "/community", label: "Komunitas", icon: "users" },
    { href: "/profile", label: "Profil", icon: "user" },
  ];

  // Streak grid (GitHub contribution style) — simulated activity.
  const weeks = 18;
  function activity(i: number): number {
    const seed = (i * 2654435761) % 100;
    if (seed < 55) return 0;
    if (seed < 75) return 1;
    if (seed < 90) return 2;
    return 3;
  }
  const intensity = ["bg-ink/5", "bg-secondary/30", "bg-secondary/55", "bg-secondary/80"];

  onMount(async () => {
    try {
      [acad, personality, badges, wallet, subjects, grades] = await Promise.all([
        api.get<AcademicDashboard>("/career/dashboard").catch(() => null),
        api.get<Personality | null>("/career/personality").catch(() => null),
        api.get<UserBadge[]>("/me/badges").catch(() => []),
        api.get<{ available: number; token_id: number }>("/wallet").catch(() => null),
        api.get<Course[]>("/courses").catch(() => []),
        api.get<Grade[]>("/career/grades").catch(() => []),
      ]);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "";
    } finally {
      loading = false;
    }
  });

  $: user = $auth.user;
</script>

<svelte:head><title>Dashboard — QLoot</title></svelte:head>

<div class="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[220px_1fr]">
  <!-- side nav -->
  <aside class="h-fit lg:sticky lg:top-28">
    <div class="card !p-3">
      {#if user}
        <div class="mb-2 px-2 py-2">
          <p class="text-sm font-semibold">{user.full_name}</p>
          <p class="text-xs muted">{user.roles.join(" · ")}</p>
        </div>
      {/if}
      <nav class="space-y-1">
        {#each sections as s}
          <a
            href={s.href}
            class="nav-active flex items-center gap-2.5 rounded-sm px-3 py-2 text-sm"
            class:!bg-transparent={s.href !== "/dashboard"}
            class:!text-current={s.href !== "/dashboard"}
          >
            <Icon name={s.icon} size="13px" />
            {s.label}
          </a>
        {/each}
      </nav>
      {#if user}
        <div class="mt-3 border-t pt-3">
          <WalletChip address={user.chain_user_ref} label="Wallet" size={30} />
        </div>
      {/if}
    </div>
  </aside>

  <!-- main -->
  <div>
    <p class="mono-label">Semester Genap 2025/2026</p>
    <h1 class="mt-1 font-display text-3xl font-bold">
      Halo, {user?.full_name?.split(" ")[0] ?? "Pelajar"}
    </h1>
    <p class="mt-1 muted">Lanjutkan belajarmu dan jaga momentum.</p>

    {#if error}
      <p class="alert-error mt-4">{error}</p>
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
          <p class="mono-label">OPC tersedia</p>
          <p class="mt-2 font-display text-3xl font-bold text-highlight">
            <StatCounter value={wallet?.available ?? 0} />
          </p>
          <p class="text-xs muted">token id {wallet?.token_id ?? 0}</p>
        </div>
        <div class="card">
          <p class="mono-label">Badge diraih</p>
          <p class="mt-2 font-display text-3xl font-bold"><StatCounter value={badges.length} /></p>
          <p class="text-xs muted">dari {7} tersedia</p>
        </div>
      </div>

      <!-- grades editor -->
      <div class="card mt-4">
        <div class="flex items-center justify-between">
          <h2 class="font-display font-bold">Nilai akademik</h2>
          <a href="/career/roadmap" class="text-xs text-primary"
            >Analisis jurusan <Icon name="arrow-right" size="10px" /></a
          >
        </div>
        <p class="mt-1 text-xs muted">
          Masukkan nilai rapor — dipakai untuk dashboard, tren, dan rekomendasi jurusan.
        </p>
        <div class="mt-3 grid gap-2 sm:grid-cols-[1fr_100px_150px_auto]">
          <select class="input" bind:value={gradeSubject}>
            {#each SUBJECTS as s}<option value={s}>{s}</option>{/each}
          </select>
          <input class="input" type="number" min="0" max="100" bind:value={gradeValue} />
          <input class="input" placeholder="2025/2026-genap" bind:value={gradeTerm} />
          <button class="btn-primary" on:click={addGrade} disabled={gradeBusy}>
            {#if gradeBusy}<Icon name="spinner" spin size="12px" />{:else}<Icon
                name="plus"
                size="12px"
              />{/if}
            Simpan
          </button>
        </div>
        {#if gradeMsg}<p class="mt-2 text-xs muted">{gradeMsg}</p>{/if}
        {#if grades.length}
          <div class="mt-3 flex flex-wrap gap-1.5">
            {#each grades as g}
              <span class="badge badge-neutral">
                {g.subject} · {g.grade}
                <span class="muted">({g.term})</span>
              </span>
            {/each}
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
          <div class="mt-4 flex flex-wrap gap-1">
            {#each Array(weeks * 7) as _, i}
              <span
                class="h-3 w-3 rounded-[3px] {intensity[activity(i)]}"
                title={`Aktivitas #${i + 1}`}
              ></span>
            {/each}
          </div>
          <div class="mt-3 flex items-center gap-2 text-xs muted">
            <span>Sedikit</span>
            {#each intensity as c}<span class="h-3 w-3 rounded-[3px] {c}"></span>{/each}
            <span>Banyak</span>
          </div>
        </div>

        <div class="card">
          <div class="flex items-center justify-between">
            <p class="mono-label">Kelas saya</p>
            <OpcChip compact={true} />
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
          <a href="/learning" class="btn-secondary mt-4 w-full">Buka pelajaran saya</a>
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
</div>
