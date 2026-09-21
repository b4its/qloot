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
</div>
