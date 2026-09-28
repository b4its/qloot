<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";

  interface Post {
    title: string;
    cat: string;
    date: string;
    icon: string;
    body: string[];
  }

  const posts: Post[] = [
    {
      title: "Cara menyusun jalur belajar yang realistis",
      cat: "Panduan",
      date: "12 Jul 2026",
      icon: "route",
      body: [
        "Mulai dari tujuan akhir, lalu pecah menjadi tonggak bulanan. Target yang jelas lebih mudah dicapai daripada rencana besar tanpa arah.",
        "Sisihkan waktu belajar pendek namun konsisten setiap hari — 30 menit konsisten mengalahkan 5 jam sekali sepekan.",
        "Tinjau kemajuan tiap pekan dan sesuaikan. Gunakan halaman Jalur Belajar dan Peringkat untuk memantau progres.",
      ],
    },
    {
      title: "5 kesalahan umum saat membuat portofolio desain",
      cat: "Desain",
      date: "2 Jul 2026",
      icon: "pen-ruler",
      body: [
        "Kesalahan terbesar adalah mulai dari visual, bukan dari masalah yang diselesaikan.",
        "Sertakan proses: riset, iterasi, dan alasan di balik keputusan desain.",
        "Batasi jumlah karya — 3 studi kasus kuat lebih baik daripada 15 karya tanpa konteks.",
      ],
    },
    {
      title: "Memahami dasar AI tanpa latar belakang matematika",
      cat: "Data & AI",
      date: "24 Jun 2026",
      icon: "microchip",
      body: [
        "AI pada dasarnya mencari pola dari data. Tidak perlu kalkulus untuk memahami alurnya.",
        "Mulai dari konsep: input, model, keluaran, dan evaluasi. Lalu naikkan kompleksitas secara bertahap.",
        "Latihan terbaik adalah mengerjakan soal dan menerima umpan balik — seperti penilaian esai berbasis AI di QLoot.",
      ],
    },
    {
      title: "Kredensial digital: apa dan mengapa penting",
      cat: "Karier",
      date: "15 Jun 2026",
      icon: "certificate",
      body: [
        "Kredensial digital adalah bukti keterampilan yang dapat diverifikasi, bukan sekadar gambar.",
        "Setiap sertifikat QLoot memiliki ID unik dan tautan verifikasi sehingga dapat dipercaya pihak lain.",
        "Karena dapat dipindahtangankan dan dipublikasikan, kredensial menjadi aset portofolio yang portabel.",
      ],
    },
  ];

  let open: number | null = null;
  function toggle(i: number) {
    open = open === i ? null : i;
  }

  // --- filter + search -------------------------------------------------------
  let catFilter = "all";
  let query = "";
  $: categories = [...new Set(posts.map((p) => p.cat))];
  $: filtered = posts.filter((p) => {
    if (catFilter !== "all" && p.cat !== catFilter) return false;
    if (query.trim()) {
      const q = query.toLowerCase().trim();
      const hay = `${p.title} ${p.cat} ${p.body.join(" ")}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  function resetFilters() {
    catFilter = "all";
    query = "";
    open = null;
  }
</script>

<svelte:head><title>Blog — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-16 sm:px-6">
  <p class="mono-label">Blog</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Wawasan, panduan, dan cerita belajar</h1>
  <p class="mt-3 max-w-2xl muted">
    Contoh artikel untuk memperlihatkan tampilan blog. Konten sebenarnya akan datang dari tim
    editorial QLoot.
  </p>

  <!-- Category filter + search -->
  <div class="mt-8 flex flex-wrap items-center gap-2">
    <div class="flex flex-wrap gap-1">
      <button
        type="button"
        class="btn-pill !py-1 text-xs"
        class:!border-primary={catFilter === "all"}
        class:!text-primary={catFilter === "all"}
        on:click={() => (catFilter = "all")}>Semua ({posts.length})</button
      >
      {#each categories as c (c)}
        <button
          type="button"
          class="btn-pill !py-1 text-xs"
          class:!border-primary={catFilter === c}
          class:!text-primary={catFilter === c}
          on:click={() => (catFilter = c)}
        >
          {c} ({posts.filter((p) => p.cat === c).length})
        </button>
      {/each}
    </div>
    <div class="relative ml-auto w-full sm:w-64">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        placeholder="Cari artikel..."
        bind:value={query}
        aria-label="Cari artikel"
      />
    </div>
  </div>

  {#if filtered.length === 0}
    <div class="card mt-6 grid place-items-center py-12 text-center">
      <p class="muted text-sm">Tidak ada artikel yang cocok dengan filtermu.</p>
      <button class="btn-ghost mt-3 !py-1 text-xs" on:click={resetFilters}>Reset Filter</button>
    </div>
  {:else}
    <div class="mt-6 grid gap-5 sm:grid-cols-2">
      {#each filtered as p, i (p.title)}
        <article use:reveal={{ delay: i * 50 }} class="card lift" data-post={p.title}>
          <div class="flex items-center justify-between">
            <span class="badge badge-indigo">{p.cat}</span>
            <span class="mono-label">{p.date}</span>
          </div>
          <div class="mt-4 flex items-start gap-3">
            <span class="tile h-10 w-10"><Icon name={p.icon} size="16px" /></span>
            <h2 class="font-display text-lg font-bold leading-snug">{p.title}</h2>
          </div>
          {#if open === i}
            <div class="mt-3 space-y-2 border-t pt-3 text-sm muted">
              {#each p.body as para}
                <p>{para}</p>
              {/each}
            </div>
          {/if}
          <button class="btn-ghost mt-4 !px-0" on:click={() => toggle(i)}>
            {open === i ? "Tutup" : "Baca selengkapnya"}
            <Icon name={open === i ? "arrow-up" : "arrow-right"} size="11px" />
          </button>
        </article>
      {/each}
    </div>
  {/if}
</div>
