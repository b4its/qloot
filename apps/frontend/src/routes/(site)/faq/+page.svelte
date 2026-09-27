<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";

  const faqs = [
    {
      q: "Apakah saya perlu latar belakang teknis?",
      a: "Tidak. Setiap pelajaran dimulai dari dasar. Materi per kelas disusun bertahap oleh pengajar.",
    },
    {
      q: "Apakah sertifikatnya diakui?",
      a: "Sertifikat QLoot adalah kredensial digital dengan ID unik dan tautan verifikasi, cocok untuk portofolio dan LinkedIn.",
    },
    {
      q: "Bagaimana QLoot diorganisir?",
      a: "QLoot adalah platform belajar berbasis kelas. Kamu melihat pelajaran, ujian, dan tugas sesuai kelas yang kamu daftarkan (mis. 1A · IPA).",
    },
    {
      q: "Apakah saya harus membayar?",
      a: "Tidak ada kursus berbayar. QLoot adalah platform kelas — akun pelajar dibuat gratis, dan akun pengajar dibuat oleh admin sekolah.",
    },
    {
      q: "Apakah ada komunitas?",
      a: "Ya. Semua pelajar dapat bergabung ke komunitas untuk diskusi dan sesi tanya-jawab mingguan.",
    },
  ];
  let open = 0;
  let query = "";
  // Filter by question or answer text.
  $: filtered = faqs.filter((f) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase().trim();
    return f.q.toLowerCase().includes(q) || f.a.toLowerCase().includes(q);
  });
</script>

<svelte:head><title>FAQ — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-16 sm:px-6">
  <p class="mono-label">Pertanyaan Umum</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Ada yang ingin ditanyakan?</h1>

  <!-- Search -->
  <div class="relative mt-6 max-w-md">
    <Icon
      name="magnifying-glass"
      size="13px"
      class="absolute left-3 top-1/2 -translate-y-1/2 muted"
    />
    <input
      class="input !pl-9"
      placeholder="Cari pertanyaan…"
      bind:value={query}
      aria-label="Cari pertanyaan"
    />
    {#if query}
      <button
        type="button"
        class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
        on:click={() => (query = "")}
        aria-label="Bersihkan pencarian"
      >
        ✕
      </button>
    {/if}
  </div>

  {#if filtered.length === 0}
    <div class="card mt-6 grid place-items-center py-12 text-center">
      <Icon name="circle-question" size="26px" class="muted" />
      <p class="mt-3 font-medium">Tidak ada pertanyaan yang cocok</p>
      <p class="text-sm muted">Coba kata kunci lain, atau tanyakan langsung di komunitas.</p>
      <a href="/community" class="btn-primary mt-4"
        ><Icon name="comment-dots" size="12px" /> Tanya di komunitas</a
      >
    </div>
  {:else}
    <div class="mt-6 card !p-0 divide-y">
      {#each filtered as f, i (f.q)}
        <div>
          <button
            class="flex w-full items-center justify-between px-5 py-4 text-left"
            on:click={() => (open = open === i ? -1 : i)}
            aria-expanded={open === i}
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
  {/if}

  <div class="card mt-6 flex flex-wrap items-center justify-between gap-4">
    <p class="text-sm muted">Masih ada pertanyaan lain?</p>
    <a href="/community" class="btn-primary"
      ><Icon name="comment-dots" size="12px" /> Tanya di komunitas</a
    >
  </div>
</div>
