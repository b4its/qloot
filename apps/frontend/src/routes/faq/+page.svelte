<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";

  const faqs = [
    {
      q: "Apakah saya perlu latar belakang teknis?",
      a: "Tidak. Setiap jalur dimulai dari dasar. Level kursus ditandai jelas: Pemula, Menengah, Lanjutan.",
    },
    {
      q: "Apakah sertifikatnya diakui?",
      a: "Sertifikat QLoot adalah kredensial digital dengan ID unik dan tautan verifikasi, cocok untuk portofolio dan LinkedIn.",
    },
    {
      q: "Berapa lama akses kursus?",
      a: "Akses selamanya untuk kursus yang kamu daftarkan, termasuk pembaruan materi.",
    },
    {
      q: "Bagaimana sistem pembayarannya?",
      a: "Beberapa kursus gratis. Untuk kursus berbayar, pembayaran dilakukan sekali di muka.",
    },
    {
      q: "Apakah ada komunitas?",
      a: "Ya. Semua pelajar dapat bergabung ke komunitas untuk diskusi dan sesi tanya-jawab mingguan.",
    },
  ];
  let open = 0;
</script>

<svelte:head><title>FAQ — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-16 sm:px-6">
  <p class="mono-label">Pertanyaan Umum</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Ada yang ingin ditanyakan?</h1>

  <div class="mt-8 card !p-0 divide-y">
    {#each faqs as f, i}
      <div>
        <button
          class="flex w-full items-center justify-between px-5 py-4 text-left"
          on:click={() => (open = open === i ? -1 : i)}
        >
          <span class="font-medium">{f.q}</span>
          <Icon name={open === i ? "minus" : "plus"} size="12px" class="text-primary" />
        </button>
        {#if open === i}
          <p class="px-5 pb-4 text-sm muted">{f.a}</p>
        {/if}
      </div>
    {/each}
  </div>

  <div class="card mt-6 flex flex-wrap items-center justify-between gap-4">
    <p class="text-sm muted">Masih ada pertanyaan lain?</p>
    <a href="/community" class="btn-primary"
      ><Icon name="comment-dots" size="12px" /> Tanya di komunitas</a
    >
  </div>
</div>
