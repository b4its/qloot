<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";

  const roles = [
    {
      title: "Senior Frontend Engineer",
      loc: "Remote · Indonesia",
      type: "Penuh waktu",
      icon: "code",
      desc: "Membangun antarmuka SvelteKit yang cepat dan aksesibel.",
    },
    {
      title: "Learning Experience Designer",
      loc: "Jakarta / Hybrid",
      type: "Penuh waktu",
      icon: "pen-ruler",
      desc: "Merancang alur belajar yang menyenangkan dan terukur.",
    },
    {
      title: "Content Creator (Data & AI)",
      loc: "Remote",
      type: "Kontrak",
      icon: "chart-line",
      desc: "Menyusun materi dan soal untuk pelajaran Data & AI.",
    },
  ];

  function applyHref(title: string): string {
    const subject = encodeURIComponent(`Lamaran: ${title}`);
    return `mailto:jobs@qloot.example?subject=${subject}`;
  }
</script>

<svelte:head><title>Karier — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-16 sm:px-6">
  <p class="mono-label">Karier</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Bangun masa depan pendidikan bersama kami</h1>
  <p class="mt-3 muted">
    Kami mencari orang yang percaya bahwa belajar bisa menyenangkan dan terukur.
  </p>

  <div class="mt-8 space-y-4">
    {#each roles as r}
      <div class="card lift">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <span class="tile h-11 w-11"><Icon name={r.icon} size="17px" /></span>
            <div>
              <p class="font-semibold">{r.title}</p>
              <p class="text-xs muted">{r.loc} · {r.type}</p>
            </div>
          </div>
          <a href={applyHref(r.title)} class="btn-secondary"
            ><Icon name="paper-plane" size="12px" /> Lamar</a
          >
        </div>
        <p class="mt-3 text-sm muted">{r.desc}</p>
      </div>
    {/each}
  </div>
</div>
