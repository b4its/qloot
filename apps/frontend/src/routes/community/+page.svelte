<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";

  const topics = [
    { name: "Desain & UX", threads: 1284, icon: "pen-ruler" },
    { name: "Data & AI", threads: 962, icon: "chart-line" },
    { name: "Web3 & Blockchain", threads: 743, icon: "cube" },
    { name: "Karier & Portofolio", threads: 588, icon: "briefcase" },
  ];

  const feed = [
    {
      author: "Alya P.",
      handle: "0xa1f4",
      time: "2 jam lalu",
      text: "Tips menyusun studi kasus portofolio: mulai dari masalah, bukan dari visual.",
      likes: 42,
      replies: 8,
    },
    {
      author: "Rangga W.",
      handle: "0x9c2b",
      time: "4 jam lalu",
      text: "Sesi minggu ini: membedah model rekomendasi sederhana. Rekaman tersedia di kelas.",
      likes: 31,
      replies: 5,
    },
    {
      author: "Nadia K.",
      handle: "0x4d18",
      time: "6 jam lalu",
      text: "Kumpulan dataset publik untuk latihan visualisasi — silakan cek tautan di ruang Data & AI.",
      likes: 57,
      replies: 12,
    },
  ];

  const leaders = [
    { rank: 1, name: "Refa Anjani", points: 4820, handle: "0x3f11" },
    { rank: 2, name: "Yoga Pratama", points: 4410, handle: "0x8d2c" },
    { rank: 3, name: "Sinta Maharani", points: 4205, handle: "0x6b7a" },
    { rank: 4, name: "Bima Aditya", points: 3980, handle: "0x2e60" },
    { rank: 5, name: "Lala Nurhaliza", points: 3760, handle: "0x9f33" },
  ];
</script>

<svelte:head><title>Komunitas — QLoot</title></svelte:head>

<section class="relative overflow-hidden border-b">
  <div class="aurora"></div>
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-14 sm:px-6">
    <p class="mono-label">Komunitas</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Belajar lebih cepat bersama</h1>
    <p class="mt-2 max-w-2xl muted">
      Diskusi, sesi tanya-jawab, dan ruang topik untuk semua pelajar QLoot.
    </p>
    <div class="mt-6 grid max-w-2xl grid-cols-2 gap-6">
      <div>
        <p class="font-display text-3xl font-bold"><StatCounter value={12840} suffix="+" /></p>
        <p class="mono-label mt-1">Anggota</p>
      </div>
      <div>
        <p class="font-display text-3xl font-bold"><StatCounter value={3577} /></p>
        <p class="mono-label mt-1">Diskusi aktif</p>
      </div>
    </div>
  </div>
</section>

<div class="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_320px]">
  <!-- feed -->
  <div class="space-y-6">
    <div class="flex flex-wrap gap-2">
      {#each topics as t}
        <span class="btn-pill"><Icon name={t.icon} size="11px" /> {t.name} · {t.threads}</span>
      {/each}
    </div>

    <div class="card">
      <div class="flex items-center gap-3">
        <span
          class="grid h-9 w-9 place-items-center rounded-full text-white"
          style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
        >
          <Icon name="user" size="13px" />
        </span>
        <input
          class="input"
          placeholder="Mulai diskusi atau ajukan pertanyaan…"
          aria-label="Tulis diskusi"
        />
        <button class="btn-primary"><Icon name="paper-plane" size="12px" /> Kirim</button>
      </div>
    </div>

    {#each feed as f}
      <article class="card">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <WalletChip
              address={`0x${f.handle.slice(2)}d41a2b3c4d5e6f708192a3b4c5d6e7f8`}
              label={f.handle}
              size={30}
            />
            <div>
              <p class="text-sm font-medium">{f.author}</p>
              <p class="text-xs muted">{f.time}</p>
            </div>
          </div>
        </div>
        <p class="mt-3 text-sm">{f.text}</p>
        <div class="mt-3 flex items-center gap-4 border-t pt-3 text-xs muted">
          <button class="inline-flex items-center gap-1.5 hover:text-primary"
            ><Icon name="heart" size="12px" /> {f.likes}</button
          >
          <button class="inline-flex items-center gap-1.5 hover:text-primary"
            ><Icon name="comment" size="12px" /> {f.replies}</button
          >
          <button class="inline-flex items-center gap-1.5 hover:text-primary"
            ><Icon name="share-nodes" size="12px" /> Bagikan</button
          >
        </div>
      </article>
    {/each}
  </div>

  <!-- leaderboard + rooms -->
  <aside class="space-y-6 h-fit lg:sticky lg:top-28">
    <div class="card">
      <p class="mono-label">Papan peringkat</p>
      <ol class="mt-3 space-y-3">
        {#each leaders as l}
          <li class="flex items-center gap-3">
            <span class="mono w-5 text-sm" class:text-highlight={l.rank <= 3}>{l.rank}</span>
            <span class="flex-1 text-sm">{l.name}</span>
            <span class="mono text-xs muted">{l.points.toLocaleString("id-ID")}</span>
          </li>
        {/each}
      </ol>
    </div>
    <div class="card">
      <p class="mono-label">Ruang topik</p>
      <ul class="mt-3 space-y-2 text-sm">
        {#each topics as t}
          <li>
            <a href="/community" class="flex items-center justify-between hover:text-primary">
              <span class="inline-flex items-center gap-2"
                ><Icon name={t.icon} size="12px" /> {t.name}</span
              >
              <Icon name="chevron-right" size="10px" />
            </a>
          </li>
        {/each}
      </ul>
    </div>
  </aside>
</div>
