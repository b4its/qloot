<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";

  const roles = [
    {
      title: "Senior Frontend Engineer",
      loc: "Remote · Indonesia",
      type: "Penuh waktu",
      icon: "code",
    },
    {
      title: "Learning Experience Designer",
      loc: "Jakarta / Hybrid",
      type: "Penuh waktu",
      icon: "pen-ruler",
    },
    { title: "Content Creator (Data & AI)", loc: "Remote", type: "Kontrak", icon: "chart-line" },
  ];
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
      <div class="card lift flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-4">
          <span class="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary"
            ><Icon name={r.icon} size="17px" /></span
          >
          <div>
            <p class="font-semibold">{r.title}</p>
            <p class="text-xs muted">{r.loc} · {r.type}</p>
          </div>
        </div>
        <a href="/about" class="btn-secondary"
          >Lihat detail <Icon name="arrow-right" size="12px" /></a
        >
      </div>
    {/each}
  </div>
</div>
