<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";

  const links = [
    {
      href: "/dashboard",
      label: "Dashboard Akademik",
      desc: "Nilai, tren, dan wawasan AI dalam satu tampilan",
      icon: "chart-column",
    },
    {
      href: "/career/personality",
      label: "Tes Kepribadian Big Five",
      desc: "Ukur 5 dimensi kepribadian (simulasi BFI-2)",
      icon: "brain",
    },
    {
      href: "/career/roadmap",
      label: "Analisis & Roadmap AI",
      desc: "Rekomendasi jurusan dan roadmap bertahap",
      icon: "compass",
    },
    {
      href: "/career/consultation",
      label: "Ruang Konsultasi BK",
      desc: "Jadwalkan sesi dan setujui analisis",
      icon: "calendar-days",
    },
    {
      href: "/career/library",
      label: "Resource Library",
      desc: "Kursus, ekstrakurikuler, dan materi belajar",
      icon: "book-open",
    },
    {
      href: "/assistant",
      label: "AI Assistant",
      desc: "Tanya seputar jurusan, kampus, dan karier",
      icon: "robot",
    },
  ];
</script>

<svelte:head><title>Panduan Karier — QLoot</title></svelte:head>

<section class="relative overflow-hidden border-b">
  <div class="aurora"></div>
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-14 sm:px-6">
    <p class="mono-label">Panduan Karier</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Rencanakan masa depanmu dengan data</h1>
    <p class="mt-2 max-w-2xl muted">
      Wawasan akademik, profil kepribadian, rekomendasi jurusan, dan roadmap bertahap — semuanya
      dalam satu tempat.
    </p>
  </div>
</section>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
    {#each links as l, i}
      <a href={l.href} use:reveal={{ delay: i * 50 }} class="card lift block">
        <span class="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary">
          <Icon name={l.icon} size="18px" />
        </span>
        <h2 class="mt-3 font-display text-lg font-bold">{l.label}</h2>
        <p class="mt-1 text-sm muted">{l.desc}</p>
        <span class="mt-3 inline-flex items-center gap-1 text-xs text-primary">
          Buka <Icon name="arrow-right" size="10px" />
        </span>
      </a>
    {/each}
  </div>
</div>
