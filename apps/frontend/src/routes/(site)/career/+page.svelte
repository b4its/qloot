<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api/client";
  import type { GradeRow, Personality, Recommendation, Milestone, Consultation } from "$lib/types";
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";

  // Live module status, so the hub is a dashboard rather than a static menu.
  let grades: GradeRow[] = [];
  let personality: Personality | null = null;
  let recommendations: Recommendation[] = [];
  let milestones: Milestone[] = [];
  let consultations: Consultation[] = [];
  let loading = true;
  // Track which modules failed so the hub can warn instead of silently
  // presenting an outage as "everything not started yet".
  let unavailable: string[] = [];

  onMount(() => {
    (async () => {
      const failures: string[] = [];
      const safe = async <T,>(p: Promise<T>, fallback: T, label: string): Promise<T> => {
        try {
          return await p;
        } catch {
          failures.push(label);
          return fallback;
        }
      };
      const [g, p, r, m, c] = await Promise.all([
        safe(api.get<GradeRow[]>("/career/grades"), [], "nilai"),
        safe(api.get<Personality | null>("/career/personality"), null, "kepribadian"),
        safe(api.get<Recommendation[]>("/career/recommendations"), [], "rekomendasi"),
        safe(api.get<Milestone[]>("/career/roadmap"), [], "peta jalan"),
        safe(api.get<Consultation[]>("/career/consultations"), [], "konsultasi"),
      ]);
      grades = g;
      personality = p;
      recommendations = r;
      milestones = m;
      consultations = c;
      unavailable = failures;
      loading = false;
    })().catch((err) => {
      console.error("Gagal memuat hub karir:", err);
      loading = false;
    });
  });

  // --- derived status --------------------------------------------------------
  $: roadmapDone = milestones.filter((m) => m.progress_percent >= 100).length;
  $: roadmapPct = milestones.length
    ? Math.round(milestones.reduce((s, m) => s + m.progress_percent, 0) / milestones.length)
    : 0;
  $: upcomingConsults = consultations.filter(
    (c) => c.status === "scheduled" || c.status === "accepted",
  ).length;
  $: approvedRecs = recommendations.filter((r) => r.status === "approved").length;

  $: roadmapStatus = milestones.length
    ? `${roadmapDone}/${milestones.length} tahap · ${roadmapPct}%`
    : recommendations.length
      ? `${recommendations.length} rekomendasi`
      : "Belum dibuat";

  $: consultStatus = upcomingConsults
    ? `${upcomingConsults} jadwal aktif`
    : consultations.length
      ? "Tidak ada jadwal aktif"
      : "Belum ada sesi";

  type Tone = "mint" | "amber" | "indigo" | "neutral";
  interface ModuleLink {
    href: string;
    label: string;
    desc: string;
    icon: string;
    status: string | null;
    statusTone: Tone;
    ready: boolean;
  }

  $: links = [
    {
      href: "/dashboard",
      label: "Dashboard Akademik",
      desc: "Nilai, tren, dan wawasan AI dalam satu tampilan",
      icon: "chart-column",
      status: grades.length ? `${grades.length} nilai` : "Belum ada nilai",
      statusTone: (grades.length ? "mint" : "neutral") as Tone,
      ready: grades.length > 0,
    },
    {
      href: "/career/personality",
      label: "Tes Kepribadian Big Five",
      desc: "Ukur 5 dimensi kepribadian (simulasi BFI-2)",
      icon: "brain",
      status: personality ? "Sudah diisi" : "Belum diisi",
      statusTone: (personality ? "mint" : "neutral") as Tone,
      ready: !!personality,
    },
    {
      href: "/career/roadmap",
      label: "Analisis & Roadmap AI",
      desc: "Rekomendasi jurusan dan roadmap bertahap",
      icon: "compass",
      status: roadmapStatus,
      statusTone: (milestones.length || recommendations.length ? "mint" : "neutral") as Tone,
      ready: milestones.length > 0 || recommendations.length > 0,
    },
    {
      href: "/career/consultation",
      label: "Ruang Konsultasi BK",
      desc: "Jadwalkan sesi dan setujui analisis",
      icon: "calendar-days",
      status: consultStatus,
      statusTone: (upcomingConsults ? "amber" : "neutral") as Tone,
      ready: upcomingConsults > 0,
    },
    {
      href: "/career/library",
      label: "Perpustakaan Sumber Daya",
      desc: "Pelajaran, ekstrakurikuler, dan materi belajar",
      icon: "book-open",
      status: null,
      statusTone: "neutral" as Tone,
      ready: false,
    },
    {
      href: "/assistant",
      label: "Asisten Qlo",
      desc: "Tanya seputar jurusan, kampus, dan karier",
      icon: "robot",
      status: null,
      statusTone: "neutral" as Tone,
      ready: false,
    },
  ] satisfies ModuleLink[];

  $: readinessSteps = [
    grades.length > 0,
    !!personality,
    milestones.length > 0 || recommendations.length > 0,
    approvedRecs > 0 || consultations.length > 0,
  ];
  $: readiness = readinessSteps.filter(Boolean).length;
  $: readinessPct = Math.round((readiness / readinessSteps.length) * 100);

  const statusClass: Record<Tone, string> = {
    mint: "badge-mint",
    amber: "badge-amber",
    indigo: "badge-indigo",
    neutral: "badge-neutral",
  };
</script>

<svelte:head><title>Panduan Karier | QLoot</title></svelte:head>

<section class="relative overflow-hidden border-b">
  <div class="aurora"></div>
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-14 sm:px-6">
    <p class="mono-label">Panduan Karier</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Rencanakan masa depanmu dengan data</h1>
    <p class="mt-2 max-w-2xl muted">
      Wawasan akademik, profil kepribadian, rekomendasi jurusan, dan roadmap bertahap: semuanya
      dalam satu tempat.
    </p>

    {#if loading}
      <div class="mt-8 grid max-w-2xl grid-cols-2 gap-3 sm:grid-cols-4">
        {#each Array(4) as _}<div class="skeleton h-24"></div>{/each}
      </div>
      <div class="mt-8 grid gap-4 sm:grid-cols-2">
        {#each Array(4) as _}<div class="skeleton h-32"></div>{/each}
      </div>
    {/if}

    {#if !loading && unavailable.length}
      <div class="alert-warning mt-4 flex items-start gap-3" role="alert" aria-live="assertive">
        <Icon name="triangle-exclamation" class="mt-0.5 flex-none" size="14px" />
        <p class="text-sm">
          Sebagian data belum dapat dimuat ({unavailable.join(", ")}). Status di bawah bisa belum
          lengkap.
        </p>
      </div>
    {/if}

    {#if !loading}
      <div class="mt-8 grid max-w-2xl grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="card p-4">
          <p class="mono-label text-[10px]">Nilai</p>
          <p class="mt-1 font-display text-2xl font-bold">{grades.length}</p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Kepribadian</p>
          <p class="mt-1 font-display text-2xl font-bold" class:text-mint={!!personality}>
            {personality ? "Siap" : "-"}
          </p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Roadmap</p>
          <p class="mt-1 font-display text-2xl font-bold" data-role="roadmap-pct">{roadmapPct}%</p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Kesiapan</p>
          <p class="mt-1 font-display text-2xl font-bold text-highlight" data-role="readiness">
            {readinessPct}%
          </p>
        </div>
      </div>
    {/if}
  </div>
</section>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
    {#each links as l, i (l.href)}
      <a href={l.href} use:reveal={{ delay: i * 50 }} class="card lift block" data-module={l.href}>
        <div class="flex items-start justify-between">
          <span class="tile h-11 w-11">
            <Icon name={l.icon} size="18px" />
          </span>
          {#if l.status}
            <span class="badge {statusClass[l.statusTone]}">
              {#if l.ready}<Icon name="circle-check" size="9px" />{/if}
              {l.status}
            </span>
          {/if}
        </div>
        <h2 class="mt-3 font-display text-lg font-bold">{l.label}</h2>
        <p class="mt-1 text-sm muted">{l.desc}</p>
        <span class="mt-3 inline-flex items-center gap-1 text-xs text-primary">
          Buka <Icon name="arrow-right" size="10px" />
        </span>
      </a>
    {/each}
  </div>
</div>
