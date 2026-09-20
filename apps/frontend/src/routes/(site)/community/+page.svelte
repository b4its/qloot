<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";
  import { auth } from "$lib/stores/auth";
  import { relativeTime } from "$lib/utils/format";

  interface Post {
    id: number;
    author: string;
    handle: string;
    at: string;
    text: string;
    likes: number;
    liked: boolean;
    replies: number;
  }

  const topics = [
    { name: "Desain & UX", threads: 1284, icon: "pen-ruler" },
    { name: "Data & AI", threads: 962, icon: "chart-line" },
    { name: "Web3 & Blockchain", threads: 743, icon: "cube" },
    { name: "Karier & Portofolio", threads: 588, icon: "briefcase" },
  ];

  let posts: Post[] = [
    {
      id: 1,
      author: "Alya P.",
      handle: "0xa1f4",
      at: new Date(Date.now() - 2 * 3600_000).toISOString(),
      text: "Tips menyusun studi kasus portofolio: mulai dari masalah, bukan dari visual.",
      likes: 42,
      liked: false,
      replies: 8,
    },
    {
      id: 2,
      author: "Rangga W.",
      handle: "0x9c2b",
      at: new Date(Date.now() - 4 * 3600_000).toISOString(),
      text: "Sesi minggu ini: membedah model rekomendasi sederhana. Rekaman tersedia di kelas.",
      likes: 31,
      liked: false,
      replies: 5,
    },
    {
      id: 3,
      author: "Nadia K.",
      handle: "0x4d18",
      at: new Date(Date.now() - 6 * 3600_000).toISOString(),
      text: "Kumpulan dataset publik untuk latihan visualisasi — silakan cek tautan di ruang Data & AI.",
      likes: 57,
      liked: false,
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

  let draft = "";
  let activeTopic = "Desain & UX";

  function post() {
    const text = draft.trim();
    if (text.length < 2) return;
    posts = [
      {
        id: Date.now(),
        author: $auth.user?.full_name ?? "Kamu",
        handle: "0x" + ($auth.user?.chain_user_ref?.slice(4, 12) ?? "kamu0"),
        at: new Date().toISOString(),
        text,
        likes: 0,
        liked: false,
        replies: 0,
      },
      ...posts,
    ];
    draft = "";
  }

  function toggleLike(p: Post) {
    p.liked = !p.liked;
    p.likes += p.liked ? 1 : -1;
    posts = [...posts];
  }
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
        <button
          class="btn-pill transition-colors"
          class:!border-primary={activeTopic === t.name}
          class:!text-primary={activeTopic === t.name}
          on:click={() => (activeTopic = t.name)}
        >
          <Icon name={t.icon} size="11px" />
          {t.name} · {t.threads}
        </button>
      {/each}
    </div>

    <div class="card">
      <div class="flex items-center gap-3">
        <span class="brand-mark-cool grid h-9 w-9 flex-none place-items-center rounded-sm">
          <Icon name="user" size="13px" />
        </span>
        <input
          class="input"
          placeholder={`Tulis diskusi di ${activeTopic}…`}
          aria-label="Tulis diskusi"
          bind:value={draft}
          on:keydown={(e) => e.key === "Enter" && post()}
        />
        <button class="btn-primary" on:click={post} disabled={draft.trim().length < 2}>
          <Icon name="paper-plane" size="12px" /> Kirim
        </button>
      </div>
    </div>

    {#each posts as f (f.id)}
      <article class="card">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <WalletChip
              address={`0x${f.handle.replace("0x", "")}d41a2b3c4d5e6f708192a3b4c5d6e7f8`}
              label={f.handle}
              size={30}
            />
            <div>
              <p class="text-sm font-medium">{f.author}</p>
              <p class="text-xs muted">{relativeTime(f.at)}</p>
            </div>
          </div>
        </div>
        <p class="mt-3 text-sm">{f.text}</p>
        <div class="mt-3 flex items-center gap-4 border-t pt-3 text-xs muted">
          <button
            class="inline-flex items-center gap-1.5 transition-colors hover:text-tertiary"
            class:text-tertiary={f.liked}
            on:click={() => toggleLike(f)}
          >
            <Icon name="heart" size="12px" />
            {f.likes}
          </button>
          <button class="inline-flex items-center gap-1.5 hover:text-primary">
            <Icon name="comment" size="12px" />
            {f.replies}
          </button>
          <button class="inline-flex items-center gap-1.5 hover:text-primary">
            <Icon name="share-nodes" size="12px" /> Bagikan
          </button>
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
            <button
              class="flex w-full items-center justify-between hover:text-primary"
              on:click={() => (activeTopic = t.name)}
            >
              <span class="inline-flex items-center gap-2"
                ><Icon name={t.icon} size="12px" /> {t.name}</span
              >
              <Icon name="chevron-right" size="10px" />
            </button>
          </li>
        {/each}
      </ul>
    </div>
  </aside>
</div>
