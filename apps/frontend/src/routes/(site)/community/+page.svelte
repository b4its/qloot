<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";
  import { api, ApiError } from "$lib/api/client";
  import { auth } from "$lib/stores/auth";
  import { relativeTime } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";

  interface Post {
    id: string;
    author_id: string;
    author_name: string;
    handle: string;
    topic: string;
    body: string;
    like_count: number;
    comment_count: number;
    liked_by_me: boolean;
    created_at: string;
    comments?: Comment[];
  }

  interface Comment {
    id: string;
    author_id: string;
    author_name: string;
    body: string;
    created_at: string;
  }

  interface Topic {
    name: string;
    posts: number;
  }

  const topicIcon: Record<string, string> = {
    Umum: "comments",
    "Desain & UX": "pen-ruler",
    "Data & AI": "chart-line",
    "Web3 & Blockchain": "cube",
    "Karier & Portofolio": "briefcase",
    "Tanya Jawab": "circle-question",
  };

  const PAGE = 15;
  let posts: Post[] = [];
  let topics: Topic[] = [];
  let stats = { members: 0, posts: 0, comments: 0 };
  let loading = true;
  let error = "";
  let draft = "";
  let posting = false;
  let activeTopic = "";
  let openComments = new Set<string>();
  let commentDraft: Record<string, string> = {};
  let busy = "";
  let page = 1;
  let hasMore = false;

  $: user = $auth.user;

  async function load() {
    loading = true;
    error = "";
    try {
      const params = new URLSearchParams({
        limit: String(PAGE),
        offset: String((page - 1) * PAGE),
      });
      if (activeTopic) params.set("topic", activeTopic);
      [posts, topics, stats] = await Promise.all([
        api.get<Post[]>(`/community/posts?${params.toString()}`),
        api.get<Topic[]>("/community/topics"),
        api.get<typeof stats>("/community/stats"),
      ]);
      hasMore = posts.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat komunitas";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    page = next;
    // Close any open comment threads when the page changes.
    openComments = new Set();
    load();
  }

  async function submitPost() {
    const text = draft.trim();
    if (text.length < 2 || posting) return;
    posting = true;
    try {
      const created = await api.post<Post>("/community/posts", {
        body: text,
        topic: activeTopic || "Umum",
      });
      // Newest-first feed: jump to page 1 so the new post is visible.
      page = 1;
      posts = [created, ...posts.slice(0, PAGE - 1)];
      hasMore = posts.length === PAGE;
      draft = "";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim";
    } finally {
      posting = false;
    }
  }

  async function toggleLike(p: Post) {
    if (!user) return;
    try {
      const updated = await api.post<Post>(`/community/posts/${p.id}/like`);
      posts = posts.map((x) => (x.id === p.id ? { ...x, ...updated } : x));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyukai kiriman";
    }
  }

  async function toggleComments(p: Post) {
    if (openComments.has(p.id)) {
      openComments = new Set([...openComments].filter((id) => id !== p.id));
      return;
    }
    openComments = new Set([...openComments, p.id]);
    await loadComments(p);
  }

  async function loadComments(p: Post) {
    try {
      const detail = await api.get<Post>(`/community/posts/${p.id}`);
      posts = posts.map((x) => (x.id === p.id ? { ...x, comments: detail.comments ?? [] } : x));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat komentar";
    }
  }

  async function submitComment(p: Post) {
    const text = (commentDraft[p.id] ?? "").trim();
    if (text.length < 1) return;
    busy = p.id;
    try {
      await api.post(`/community/posts/${p.id}/comments`, { body: text });
      commentDraft = { ...commentDraft, [p.id]: "" };
      // Ensure the thread stays open and shows the new comment. Calling the
      // toggle twice (as before) net-closed it, so refresh directly instead.
      openComments = new Set([...openComments, p.id]);
      await loadComments(p);
      posts = posts.map((x) => (x.id === p.id ? { ...x, comment_count: x.comment_count + 1 } : x));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim komentar";
    } finally {
      busy = "";
    }
  }

  function pickTopic(name: string) {
    // Re-clicking the active topic clears the filter (back to "Semua").
    activeTopic = activeTopic === name ? "" : name;
    page = 1;
    openComments = new Set();
    load();
  }

  function clearTopic() {
    if (!activeTopic) return;
    activeTopic = "";
    page = 1;
    openComments = new Set();
    load();
  }

  onMount(load);
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
    <div class="mt-6 grid max-w-2xl grid-cols-2 gap-6 sm:grid-cols-3">
      <div>
        <p class="font-display text-3xl font-bold"><StatCounter value={stats.members} /></p>
        <p class="mono-label mt-1">Anggota</p>
      </div>
      <div>
        <p class="font-display text-3xl font-bold"><StatCounter value={stats.posts} /></p>
        <p class="mono-label mt-1">Diskusi</p>
      </div>
      <div>
        <p class="font-display text-3xl font-bold"><StatCounter value={stats.comments} /></p>
        <p class="mono-label mt-1">Komentar</p>
      </div>
    </div>
  </div>
</section>

<div class="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_320px]">
  <!-- feed -->
  <div class="space-y-6">
    <div class="flex flex-wrap gap-2">
      <button
        class="btn-pill transition-colors"
        class:!border-primary={!activeTopic}
        class:!text-primary={!activeTopic}
        on:click={clearTopic}
      >
        <Icon name="layer-group" size="11px" /> Semua
      </button>
      {#each topics as t}
        <button
          class="btn-pill transition-colors"
          class:!border-primary={activeTopic === t.name}
          class:!text-primary={activeTopic === t.name}
          on:click={() => pickTopic(t.name)}
        >
          <Icon name={topicIcon[t.name] ?? "hashtag"} size="11px" />
          {t.name} · {t.posts}
        </button>
      {/each}
    </div>

    {#if error}
      <p class="alert-error">{error}</p>
    {/if}

    <div class="card">
      <div class="flex items-center gap-3">
        <span class="brand-mark-cool grid h-9 w-9 flex-none place-items-center rounded-sm">
          <Icon name="user" size="13px" />
        </span>
        <input
          class="input"
          placeholder={activeTopic ? `Tulis diskusi di ${activeTopic}…` : "Tulis diskusi…"}
          aria-label="Tulis diskusi"
          bind:value={draft}
          on:keydown={(e) => e.key === "Enter" && submitPost()}
        />
        <button
          class="btn-primary flex-none"
          on:click={submitPost}
          disabled={posting || draft.trim().length < 2}
        >
          {#if posting}<Icon name="spinner" spin size="12px" />{:else}<Icon
              name="paper-plane"
              size="12px"
            />{/if}
          Kirim
        </button>
      </div>
    </div>

    {#if loading}
      {#each Array(3) as _}<div class="skeleton h-28"></div>{/each}
    {:else if posts.length === 0}
      <div class="card grid place-items-center py-14 text-center">
        <Icon name="comments" size="26px" class="muted" />
        <p class="mt-3 font-semibold">Belum ada diskusi</p>
        <p class="text-sm muted">Jadilah yang pertama memulai percakapan.</p>
      </div>
    {:else}
      {#each posts as f (f.id)}
        <article class="card">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <WalletChip address={f.handle} label={f.author_name} size={30} />
              <div>
                <p class="text-sm font-medium">{f.author_name}</p>
                <p class="text-xs muted">
                  {relativeTime(f.created_at)} · <span class="text-secondary">{f.topic}</span>
                </p>
              </div>
            </div>
          </div>
          <p class="mt-3 text-sm">{f.body}</p>
          <div class="mt-3 flex items-center gap-4 border-t pt-3 text-xs muted">
            <button
              class="inline-flex items-center gap-1.5 transition-colors hover:text-tertiary"
              class:text-tertiary={f.liked_by_me}
              on:click={() => toggleLike(f)}
            >
              <Icon name={f.liked_by_me ? "heart" : "heart"} size="12px" />
              {f.like_count}
            </button>
            <button
              class="inline-flex items-center gap-1.5 hover:text-primary"
              on:click={() => toggleComments(f)}
            >
              <Icon name="comment" size="12px" />
              {f.comment_count}
            </button>
            <button
              class="inline-flex items-center gap-1.5 hover:text-primary"
              on:click={() =>
                navigator.clipboard?.writeText(`${location.origin}/community#${f.id}`)}
            >
              <Icon name="share-nodes" size="12px" /> Bagikan
            </button>
          </div>

          {#if openComments.has(f.id)}
            <div class="mt-3 space-y-3 border-t pt-3">
              {#each f.comments ?? [] as c (c.id)}
                <div class="flex items-start gap-2 text-sm">
                  <Icon name="user" size="11px" class="mt-1 muted" />
                  <div>
                    <p>
                      <span class="font-medium">{c.author_name}</span>
                      <span class="text-xs muted"> · {relativeTime(c.created_at)}</span>
                    </p>
                    <p class="text-ink2">{c.body}</p>
                  </div>
                </div>
              {/each}
              {#if (f.comments ?? []).length === 0}
                <p class="text-xs muted">Belum ada komentar.</p>
              {/if}
              <div class="flex items-center gap-2">
                <input
                  class="input !py-1.5 text-sm"
                  placeholder="Tulis komentar…"
                  bind:value={commentDraft[f.id]}
                  on:keydown={(e) => e.key === "Enter" && submitComment(f)}
                />
                <button
                  class="btn-secondary flex-none !py-1.5"
                  on:click={() => submitComment(f)}
                  disabled={busy === f.id}
                >
                  <Icon name="paper-plane" size="11px" />
                </button>
              </div>
            </div>
          {/if}
        </article>
      {/each}
      <Pagination
        {page}
        pageSize={PAGE}
        {hasMore}
        {loading}
        label="diskusi"
        onPrev={() => go(-1)}
        onNext={() => go(1)}
      />
    {/if}
  </div>

  <!-- topics sidebar -->
  <aside class="space-y-6 h-fit lg:sticky lg:top-28">
    <div class="card">
      <p class="mono-label">Ruang topik</p>
      <ul class="mt-3 space-y-2 text-sm">
        {#each topics as t}
          <li>
            <button
              class="flex w-full items-center justify-between hover:text-primary"
              on:click={() => pickTopic(t.name)}
            >
              <span class="inline-flex items-center gap-2"
                ><Icon name={topicIcon[t.name] ?? "hashtag"} size="12px" /> {t.name}</span
              >
              <span class="mono text-xs muted">{t.posts}</span>
            </button>
          </li>
        {/each}
      </ul>
    </div>
    <div class="card">
      <p class="mono-label">Panduan komunitas</p>
      <ul class="mt-3 space-y-2 text-sm muted">
        <li class="flex items-start gap-2">
          <Icon name="circle-check" class="mt-0.5 text-secondary" size="11px" /> Saling menghargai.
        </li>
        <li class="flex items-start gap-2">
          <Icon name="circle-check" class="mt-0.5 text-secondary" size="11px" /> Sertakan sumber bila
          berbagi materi.
        </li>
        <li class="flex items-start gap-2">
          <Icon name="circle-check" class="mt-0.5 text-secondary" size="11px" /> Satu topik per diskusi.
        </li>
      </ul>
    </div>
  </aside>
</div>
