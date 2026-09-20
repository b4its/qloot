<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
</script>

<svelte:head><title>Tentang — QLoot</title></svelte:head>

<section class="relative overflow-hidden border-b">
  <div class="aurora"></div>
  <div class="relative z-10 mx-auto max-w-4xl px-4 py-16 sm:px-6">
    <p class="mono-label">Tentang</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Belajar seharusnya terasa seperti kemajuan</h1>
    <p class="mt-3 muted">
      QLoot dibangun untuk membuat pembelajaran terstruktur, terukur, dan menyenangkan — dengan
      teknologi sebagai alat, bukan tujuan.
    </p>
  </div>
</section>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <div class="grid gap-6 sm:grid-cols-3">
    {#each [{ icon: "bullseye", title: "Misi", text: "Membuka akses pembelajaran berkualitas untuk siapa saja, di mana saja." }, { icon: "eye", title: "Visi", text: "Menjadi ruang belajar pilihan bagi talenta digital Indonesia." }, { icon: "heart", title: "Nilai", text: "Jelas, jujur, dan berpusat pada kemajuan pelajar." }] as v}
      <div class="card lift">
        <span class="tile h-11 w-11"><Icon name={v.icon} size="18px" /></span>
        <h2 class="mt-3 font-display text-lg font-bold">{v.title}</h2>
        <p class="mt-1 text-sm muted">{v.text}</p>
      </div>
    {/each}
  </div>

  <div class="mt-10 grid grid-cols-2 gap-6 rounded-sm border p-6 sm:grid-cols-4">
    {#each [{ v: 12840, s: "+", l: "Pelajar" }, { v: 96, s: "", l: "Kursus" }, { v: 42, s: "", l: "Mentor" }, { v: 5310, s: "+", l: "Sertifikat" }] as s}
      <div>
        <p class="font-display text-2xl font-bold"><StatCounter value={s.v} suffix={s.s} /></p>
        <p class="mono-label mt-1">{s.l}</p>
      </div>
    {/each}
  </div>
</div>
