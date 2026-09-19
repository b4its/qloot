<script lang="ts">
  import { page } from "$app/stores";
  import Icon from "$lib/components/Icon.svelte";
  import ProgressRing from "$lib/components/ProgressRing.svelte";
  import CertificateBadge from "$lib/components/CertificateBadge.svelte";
  import { learningPaths, courses } from "$lib/data/content";

  $: slug = $page.params.slug;
  $: path = learningPaths.find((p) => p.slug === slug);
  // Simple simulation: show courses sequentially for this path.
  $: pathCourses = courses.slice(0, path?.courses ?? 4);
</script>

<svelte:head><title>{path ? path.title : "Jalur Belajar"} — QLoot</title></svelte:head>

{#if path}
  <section class="relative overflow-hidden border-b">
    <div class="aurora"></div>
    <div class="relative z-10 mx-auto max-w-7xl px-4 py-12 sm:px-6">
      <a href="/paths" class="text-xs muted hover:text-primary">← Semua jalur</a>
      <div class="mt-4 flex flex-wrap items-center gap-4">
        <span
          class="grid h-14 w-14 place-items-center rounded-hero text-white"
          style={`background-image:${path.accent}`}
        >
          <Icon name={path.icon} size="22px" />
        </span>
        <div>
          <h1 class="font-display text-3xl font-bold">{path.title}</h1>
          <p class="muted">{path.desc}</p>
        </div>
      </div>
      <div class="mono-label mt-5 flex flex-wrap items-center gap-4">
        <span>{path.courses} kursus</span><span>·</span><span>{path.weeks} minggu</span><span
          >·</span
        ><span>{path.level}</span>
      </div>
    </div>
  </section>

  <div class="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_300px]">
    <!-- timeline -->
    <ol class="relative space-y-6 border-l pl-6">
      {#each pathCourses as c, i}
        <li class="relative">
          <span
            class="absolute -left-[34px] grid h-6 w-6 place-items-center rounded-full text-[10px] font-bold text-white"
            style={`background-image:${c.accent}`}
          >
            {i + 1}
          </span>
          <a href={`/courses/${c.slug}`} class="card lift block">
            <div class="flex items-start justify-between gap-4">
              <div>
                <span class="badge badge-neutral">{c.category}</span>
                <p class="mt-2 font-display text-lg font-bold">{c.title}</p>
                <p class="text-sm muted">{c.tagline}</p>
              </div>
              <Icon name={c.icon} size="26px" class="text-primary/60" />
            </div>
            <div class="mono-label mt-3 flex items-center gap-3">
              <span>{c.level}</span><span>·</span><span>{c.weeks} minggu</span>
            </div>
          </a>
        </li>
      {/each}
    </ol>

    <!-- side: progress + badge -->
    <aside class="space-y-6 lg:sticky lg:top-28 h-fit">
      <div class="card grid place-items-center py-6">
        <ProgressRing value={35} label="Progres" sublabel="simulasi" />
        <p class="mono-label mt-3">2 dari {path.courses} kursus selesai</p>
      </div>
      <div class="card">
        <p class="mono-label">Badge yang akan diperoleh</p>
        <div class="mt-3">
          <CertificateBadge
            title={path.title}
            subtitle="Kredensial jalur lengkap"
            edition="#0000 / 5000"
            icon={path.icon}
            compact
          />
        </div>
      </div>
    </aside>
  </div>
{:else}
  <div class="mx-auto max-w-xl px-4 py-24 text-center">
    <Icon name="circle-question" size="32px" class="muted" />
    <h1 class="mt-4 font-display text-2xl font-bold">Jalur tidak ditemukan</h1>
    <a href="/paths" class="btn-primary mt-6">Kembali</a>
  </div>
{/if}
