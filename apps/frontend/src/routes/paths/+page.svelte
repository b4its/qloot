<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";
  import { learningPaths } from "$lib/data/content";
</script>

<svelte:head><title>Jalur Belajar — QLoot</title></svelte:head>

<div class="dotgrid relative">
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-12 sm:px-6">
    <p class="mono-label">Jalur Belajar</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Rencana belajar yang terarah</h1>
    <p class="mt-2 max-w-2xl muted">
      Susunan kursus berurutan untuk membawamu dari dasar hingga siap kerja. Setiap jalur diakhiri
      sertifikat digital.
    </p>

    <div class="mt-8 grid gap-6 sm:grid-cols-2">
      {#each learningPaths as p, i}
        <a href={`/paths/${p.slug}`} use:reveal={{ delay: i * 60 }} class="grad-border lift block">
          <span class="block p-6">
            <span class="flex items-center justify-between">
              <span
                class="grid h-12 w-12 place-items-center rounded-xl text-white"
                style={`background-image:${p.accent}`}
              >
                <Icon name={p.icon} size="20px" />
              </span>
              <span class="badge badge-indigo">{p.level}</span>
            </span>
            <span class="mt-4 block font-display text-xl font-bold">{p.title}</span>
            <span class="mt-1 block text-sm muted">{p.desc}</span>
            <span class="mono-label mt-5 flex items-center gap-3">
              <span>{p.courses} kursus</span><span>·</span><span>{p.weeks} minggu</span>
            </span>
          </span>
        </a>
      {/each}
    </div>
  </div>
</div>
