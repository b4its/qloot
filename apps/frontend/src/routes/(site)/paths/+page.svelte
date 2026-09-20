<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";
  import { classTracks } from "$lib/data/content";

  // Subject groupings across classes (derived from the class tracks).
  const seen = new Map<string, { name: string; classes: string[] }>();
  for (const t of classTracks) {
    for (const s of t.subjects) {
      const e = seen.get(s) ?? { name: s, classes: [] };
      e.classes.push(t.code);
      seen.set(s, e);
    }
  }
  const subjects = [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
</script>

<svelte:head><title>Mata Pelajaran — QLoot</title></svelte:head>

<div class="dotgrid relative">
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-12 sm:px-6">
    <p class="mono-label">Kurikulum</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Mata pelajaran</h1>
    <p class="mt-2 max-w-2xl muted">
      Daftar mata pelajaran yang diajarkan, beserta kelas tempat pelajaran tersebut dibuka.
    </p>

    <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {#each subjects as s, i}
        <a href="/courses" use:reveal={{ delay: i * 50 }} class="card lift block">
          <span class="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary">
            <Icon name="book-open-reader" size="18px" />
          </span>
          <h2 class="mt-3 font-display text-lg font-bold">{s.name}</h2>
          <p class="mono-label mt-1">Diajarkan di kelas</p>
          <div class="mt-2 flex flex-wrap gap-1.5">
            {#each s.classes as c}<span class="badge badge-indigo">Kelas {c}</span>{/each}
          </div>
        </a>
      {/each}
    </div>
  </div>
</div>
