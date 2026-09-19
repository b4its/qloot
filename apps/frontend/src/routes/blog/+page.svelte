<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";

  const posts = [
    {
      title: "Cara menyusun jalur belajar yang realistis",
      cat: "Panduan",
      date: "12 Jul 2026",
      icon: "route",
    },
    {
      title: "5 kesalahan umum saat membuat portofolio desain",
      cat: "Desain",
      date: "2 Jul 2026",
      icon: "pen-ruler",
    },
    {
      title: "Memahami dasar AI tanpa latar belakang matematika",
      cat: "Data & AI",
      date: "24 Jun 2026",
      icon: "microchip",
    },
    {
      title: "Kredensial digital: apa dan mengapa penting",
      cat: "Karier",
      date: "15 Jun 2026",
      icon: "certificate",
    },
  ];
</script>

<svelte:head><title>Blog — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-16 sm:px-6">
  <p class="mono-label">Blog</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Wawasan, panduan, dan cerita belajar</h1>

  <div class="mt-8 grid gap-5 sm:grid-cols-2">
    {#each posts as p, i}
      <article use:reveal={{ delay: i * 50 }} class="card lift">
        <div class="flex items-center justify-between">
          <span class="badge badge-indigo">{p.cat}</span>
          <span class="mono-label">{p.date}</span>
        </div>
        <div class="mt-4 flex items-start gap-3">
          <span
            class="grid h-10 w-10 flex-none place-items-center rounded-xl bg-primary/10 text-primary"
            ><Icon name={p.icon} size="16px" /></span
          >
          <h2 class="font-display text-lg font-bold leading-snug">{p.title}</h2>
        </div>
        <a href="/blog" class="btn-ghost mt-4 !px-0"
          >Baca selengkapnya <Icon name="arrow-right" size="11px" /></a
        >
      </article>
    {/each}
  </div>
</div>
