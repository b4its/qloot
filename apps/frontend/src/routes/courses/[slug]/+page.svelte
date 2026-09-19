<script lang="ts">
  import { page } from "$app/stores";
  import Icon from "$lib/components/Icon.svelte";
  import CertificateBadge from "$lib/components/CertificateBadge.svelte";
  import { courses, formatIDR } from "$lib/data/content";

  $: slug = $page.params.slug;
  $: course = courses.find((c) => c.slug === slug);

  let tab = "overview";
  const tabs = [
    { key: "overview", label: "Ikhtisar", icon: "circle-info" },
    { key: "curriculum", label: "Kurikulum", icon: "list-ol" },
    { key: "mentor", label: "Instruktur", icon: "user-tie" },
    { key: "reviews", label: "Ulasan", icon: "comment-dots" },
    { key: "certificate", label: "Sertifikat", icon: "certificate" },
  ];

  const curriculum = [
    { title: "Pengenalan & Persiapan", lessons: 4, minutes: 38 },
    { title: "Konsep Inti", lessons: 6, minutes: 96 },
    { title: "Studi Kasus", lessons: 5, minutes: 72 },
    { title: "Proyek Akhir", lessons: 3, minutes: 120 },
  ];
  let openModule = 0;

  const skills = [
    "Berpikir sistem",
    "Prototyping",
    "Kolaborasi",
    "Dokumentasi",
    "Presentasi",
    "Problem solving",
  ];

  const reviews = [
    { name: "Ariq", rating: 5, text: "Materinya runtut dan proyeknya relevan dengan industri." },
    { name: "Lala", rating: 5, text: "Mentor responsif, penjelasan mudah dipahami." },
    { name: "Dimas", rating: 4, text: "Bagus, akan lebih baik dengan studi kasus tambahan." },
  ];

  $: totalLessons = curriculum.reduce((s, m) => s + m.lessons, 0);
  $: totalMinutes = curriculum.reduce((s, m) => s + m.minutes, 0);
</script>

<svelte:head><title>{course ? course.title : "Kursus"} — QLoot</title></svelte:head>

{#if course}
  <!-- HERO SPLIT -->
  <section class="relative overflow-hidden border-b">
    <div class="aurora"></div>
    <div
      class="relative z-10 mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_380px]"
    >
      <div>
        <div class="flex items-center gap-2 text-xs muted">
          <a href="/courses" class="hover:text-primary">Katalog</a>
          <Icon name="chevron-right" size="9px" />
          <span>{course.category}</span>
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-2">
          <span class="badge badge-indigo">{course.category}</span>
          <span class="badge badge-neutral">{course.level}</span>
        </div>
        <h1 class="mt-4 font-display text-3xl font-bold leading-tight sm:text-4xl">
          {course.title}
        </h1>
        <p class="mt-3 max-w-2xl text-ink2">{course.tagline}</p>

        <div class="mt-4 flex flex-wrap items-center gap-4 text-sm muted">
          <span class="inline-flex items-center gap-1.5">
            <Icon name="star" class="text-highlight" size="12px" />
            {course.rating} rating
          </span>
          <span class="inline-flex items-center gap-1.5">
            <Icon name="users" size="12px" />
            {course.students.toLocaleString("id-ID")} pelajar
          </span>
          <span class="inline-flex items-center gap-1.5">
            <Icon name="clock" size="12px" />
            {course.weeks} minggu · {course.hoursPerWeek} jam/minggu
          </span>
        </div>

        <div class="mt-5 flex items-center gap-3">
          <span
            class="grid h-10 w-10 place-items-center rounded-full font-display text-sm font-bold text-white"
            style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
          >
            {course.mentor
              .split(" ")
              .map((n) => n[0])
              .slice(0, 2)
              .join("")}
          </span>
          <div>
            <p class="text-sm font-medium">{course.mentor}</p>
            <p class="text-xs muted">Praktisi aktif</p>
          </div>
        </div>
      </div>

      <!-- sticky enroll card -->
      <div class="lg:sticky lg:top-28 h-fit">
        <div class="grad-border">
          <div class="card">
            <div
              class="grid h-40 place-items-center rounded-hero"
              style={`background-image:${course.accent}`}
            >
              <span
                class="grid h-14 w-14 place-items-center rounded-full bg-white/20 backdrop-blur"
              >
                <Icon name="play" size="20px" class="text-white" />
              </span>
            </div>
            <div class="mt-4 flex items-baseline justify-between">
              <span class="font-display text-2xl font-bold">{formatIDR(course.price)}</span>
              {#if course.price > 0}
                <span class="text-xs muted line-through"
                  >Rp{((course.price * 1.4) / 1000).toFixed(0)}rb</span
                >
              {/if}
            </div>
            <a href="/register" class="btn-primary mt-4 w-full">
              <Icon name="bolt" size="13px" />
              {course.price === 0 ? "Mulai Gratis" : "Daftar Sekarang"}
            </a>
            <a href={`/paths`} class="btn-secondary mt-2 w-full">Lihat jalur terkait</a>
            <ul class="mt-4 space-y-2 border-t pt-4 text-sm">
              <li class="flex items-center gap-2">
                <Icon name="video" class="text-primary" size="12px" />
                {totalLessons} pelajaran video
              </li>
              <li class="flex items-center gap-2">
                <Icon name="certificate" class="text-primary" size="12px" /> Sertifikat digital
              </li>
              <li class="flex items-center gap-2">
                <Icon name="infinity" class="text-primary" size="12px" /> Akses selamanya
              </li>
              <li class="flex items-center gap-2">
                <Icon name="language" class="text-primary" size="12px" /> Bahasa Indonesia
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- TABS -->
  <div class="mx-auto max-w-7xl px-4 py-10 sm:px-6">
    <div class="flex flex-wrap gap-1 border-b">
      {#each tabs as t}
        <button
          class="inline-flex items-center gap-2 px-4 py-2.5 text-sm transition-colors"
          class:border-b-2={tab === t.key}
          class:border-primary={tab === t.key}
          class:font-semibold={tab === t.key}
          on:click={() => (tab = t.key)}
        >
          <Icon name={t.icon} size="12px" />
          {t.label}
        </button>
      {/each}
    </div>

    <div class="mt-6">
      {#if tab === "overview"}
        <div class="grid gap-6 lg:grid-cols-3">
          <div class="lg:col-span-2 space-y-6">
            <div class="card">
              <h2 class="font-display text-xl font-bold">Tentang kursus ini</h2>
              <p class="mt-2 text-sm muted">
                Kursus ini membimbingmu langkah demi langkah dengan pendekatan praktik. Setiap modul
                diakhiri latihan dan studi kasus nyata, sehingga kamu membangun portofolio selepas
                selesai.
              </p>
            </div>
            <div class="card">
              <h2 class="font-display text-xl font-bold">Skill yang didapat</h2>
              <div class="mt-3 flex flex-wrap gap-2">
                {#each skills as s}<span class="btn-pill">{s}</span>{/each}
              </div>
            </div>
          </div>
          <div class="card h-fit">
            <p class="mono-label">Ringkasan</p>
            <ul class="mt-3 space-y-3 text-sm">
              <li class="flex items-center justify-between">
                <span class="muted">Level</span><span>{course.level}</span>
              </li>
              <li class="flex items-center justify-between">
                <span class="muted">Durasi</span><span>{course.weeks} minggu</span>
              </li>
              <li class="flex items-center justify-between">
                <span class="muted">Beban</span><span>{course.hoursPerWeek} jam/minggu</span>
              </li>
              <li class="flex items-center justify-between">
                <span class="muted">Pelajaran</span><span>{totalLessons}</span>
              </li>
              <li class="flex items-center justify-between">
                <span class="muted">Total waktu</span><span
                  >{Math.round(totalMinutes / 60)} jam</span
                >
              </li>
            </ul>
          </div>
        </div>
      {:else if tab === "curriculum"}
        <div class="card !p-0 divide-y">
          {#each curriculum as m, i}
            <div>
              <button
                class="flex w-full items-center justify-between px-5 py-4 text-left"
                on:click={() => (openModule = openModule === i ? -1 : i)}
              >
                <span class="flex items-center gap-3">
                  <span class="mono-label">{String(i + 1).padStart(2, "0")}</span>
                  <span class="font-medium">{m.title}</span>
                </span>
                <span class="flex items-center gap-3 text-xs muted">
                  <span>{m.lessons} pelajaran · {m.minutes} menit</span>
                  <Icon name={openModule === i ? "chevron-up" : "chevron-down"} size="12px" />
                </span>
              </button>
              {#if openModule === i}
                <ul class="space-y-2 px-5 pb-4 pl-14 text-sm">
                  {#each Array(m.lessons) as _, j}
                    <li class="flex items-center gap-3 muted">
                      <Icon name="circle-play" class="text-primary" size="11px" />
                      Pelajaran {i + 1}.{j + 1}
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
          {/each}
        </div>
      {:else if tab === "mentor"}
        <div class="card flex flex-col gap-4 sm:flex-row sm:items-center">
          <span
            class="grid h-16 w-16 place-items-center rounded-full font-display text-xl font-bold text-white"
            style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
          >
            {course.mentor
              .split(" ")
              .map((n) => n[0])
              .slice(0, 2)
              .join("")}
          </span>
          <div>
            <p class="font-display text-lg font-bold">{course.mentor}</p>
            <p class="text-sm muted">
              Praktisi aktif dengan pengalaman membangun produk nyata di industri.
            </p>
          </div>
        </div>
      {:else if tab === "reviews"}
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {#each reviews as r}
            <figure class="card">
              <div class="flex items-center gap-1">
                {#each Array(5) as _, i}
                  <Icon
                    name="star"
                    size="12px"
                    class={i < r.rating ? "text-highlight" : "opacity-25"}
                  />
                {/each}
              </div>
              <blockquote class="mt-2 text-sm">{r.text}</blockquote>
              <figcaption class="mt-2 text-xs muted">{r.name}</figcaption>
            </figure>
          {/each}
        </div>
      {:else if tab === "certificate"}
        <div class="grid gap-6 lg:grid-cols-2">
          <div>
            <h2 class="font-display text-xl font-bold">Sertifikat digital</h2>
            <p class="mt-2 text-sm muted">
              Setelah menyelesaikan seluruh modul, kamu menerima sertifikat dengan ID unik dan
              tautan verifikasi yang dapat dibagikan.
            </p>
          </div>
          <CertificateBadge
            title={course.title}
            subtitle="Contoh sertifikat kelulusan"
            edition="#0001 / 5000"
            icon={course.icon}
          />
        </div>
      {/if}
    </div>
  </div>
{:else}
  <div class="mx-auto max-w-xl px-4 py-24 text-center">
    <Icon name="circle-question" size="32px" class="muted" />
    <h1 class="mt-4 font-display text-2xl font-bold">Kursus tidak ditemukan</h1>
    <p class="mt-2 muted">Kursus yang kamu cari mungkin sudah dipindahkan.</p>
    <a href="/courses" class="btn-primary mt-6">Kembali ke katalog</a>
  </div>
{/if}
