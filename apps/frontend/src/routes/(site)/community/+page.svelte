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
    parent_id?: string | null;
    edited_at?: string | null;
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
  // COMM-05: feed ranking — newest (default), hot (decayed engagement), top.
  let sort: "new" | "hot" | "top" = "new";
  // COMM-06: restrict the feed to authors the viewer follows.
  let followingOnly = false;
  let followingIds: string[] = [];
  let openComments = new Set<string>();
  let commentDraft: Record<string, string> = {};
  let busy = "";
  let page = 1;
  let hasMore = false;
  /** Post id whose share link was just copied (shows a transient "Tersalin"). */
  let copiedId = "";

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
      params.set("sort", sort);
      if (followingOnly) params.set("following", "true");
      [posts, topics, stats] = await Promise.all([
        api.get<Post[]>(`/community/posts?${params.toString()}`),
        api.get<Topic[]>("/community/topics"),
        api.get<typeof stats>("/community/stats"),
      ]);
      if (user) {
        followingIds = await api.get<string[]>("/me/following").catch(() => []);
      }
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
    if (!user || busy === `like-${p.id}`) return;
    busy = `like-${p.id}`;
    try {
      const updated = await api.post<Post>(`/community/posts/${p.id}/like`);
      posts = posts.map((x) => (x.id === p.id ? { ...x, ...updated } : x));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyukai kiriman";
    } finally {
      busy = "";
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

  /** Copy a deep link to a post (matches the rendered `id="post-<id>"` anchor). */
  async function sharePost(id: string) {
    const url = `${location.origin}/community#post-${id}`;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        // Fallback for browsers without the async Clipboard API.
        const el = document.createElement("textarea");
        el.value = url;
        el.style.position = "fixed";
        el.style.opacity = "0";
        document.body.appendChild(el);
        el.select();
        document.execCommand("copy");
        document.body.removeChild(el);
      }
      copiedId = id;
      setTimeout(() => {
        if (copiedId === id) copiedId = "";
      }, 2000);
    } catch {
      error = "Gagal menyalin tautan";
    }
  }

  /** COMM-04: escape the body, then link @mentions (injection-safe). */
  function renderBody(body: string): string {
    const escaped = (body ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return escaped.replace(
      /@([A-Za-z0-9_.\- ]{2,64}?)(?=[,.!?;:\n]|$)/g,
      (_m, name) =>
        `<a class="text-primary hover:underline" href="/community?mention=${encodeURIComponent(
          name.trim(),
        )}">@${name.trim()}</a>`,
    );
  }

  /** COMM-02: reply to a specific comment (nested). */
  async function replyTo(p: Post, parentId: string) {
    const text = prompt("Balasan Anda?");
    if (!text || text.trim().length < 1) return;
    error = "";
    try {
      await api.post(`/community/posts/${p.id}/comments`, {
        body: text.trim(),
        parent_id: parentId,
      });
      await loadComments(p);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membalas";
    }
  }

  /** COMM-02: edit your own comment. */
  async function editComment(p: Post, c: Comment) {
    const text = prompt("Ubah komentar", c.body);
    if (!text || text.trim().length < 1 || text === c.body) return;
    error = "";
    try {
      await api.patch(`/community/comments/${c.id}`, { body: text.trim() });
      await loadComments(p);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah komentar";
    }
  }

  /** COMM-06: follow/unfollow a post author. */
  async function toggleFollow(authorId: string) {
    if (!user || authorId === user.id) return;
    error = "";
    try {
      const status = followingIds.includes(authorId)
        ? await api.delete<{ is_following: boolean }>(`/users/${authorId}/follow`)
        : await api.post<{ is_following: boolean }>(`/users/${authorId}/follow`);
      followingIds = status.is_following
        ? [...followingIds, authorId]
        : followingIds.filter((id) => id !== authorId);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui ikutan";
    }
  }

  /** COMM-01: report a post or comment (one report per object). */
  async function reportTarget(targetType: "post" | "comment", targetId: string) {
    const reason = prompt("Alasan melaporkan konten ini?");
    if (!reason || reason.trim().length < 3) return;
    error = "";
    try {
      await api.post("/community/reports", {
        target_type: targetType,
        target_id: targetId,
        reason: reason.trim(),
      });
      copiedId = targetId;
      setTimeout(() => {
        if (copiedId === targetId) copiedId = "";
      }, 2000);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal melaporkan konten";
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

  /** Delete your own comment (or any, as an admin). */
  async function deleteComment(p: Post, c: Comment) {
    if (!confirm("Hapus komentar ini?")) return;
    busy = `cd-${c.id}`;
    try {
      await api.delete(`/community/comments/${c.id}`);
      posts = posts.map((x) =>
        x.id === p.id ? { ...x, comment_count: Math.max(0, x.comment_count - 1) } : x,
      );
      await loadComments(p);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus komentar";
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

    <div class="mt-3 flex flex-wrap items-center gap-2 text-xs">
      <span class="muted">Urutkan:</span>
      {#each [["new", "Terbaru"], ["hot", "Populer"], ["top", "Teratas"]] as [key, label]}
        <button
          class="btn-pill !py-1"
          class:!border-primary={sort === key}
          class:!text-primary={sort === key}
          on:click={() => {
            sort = key as "new" | "hot" | "top";
            page = 1;
            load();
          }}
        >
          {label}
        </button>
      {/each}
      <span class="mx-1 muted">·</span>
      <button
        class="btn-pill !py-1"
        class:!border-primary={followingOnly}
        class:!text-primary={followingOnly}
        aria-pressed={followingOnly}
        on:click={() => {
          followingOnly = !followingOnly;
          page = 1;
          load();
        }}
      >
        <Icon name="user-check" size="11px" /> Mengikuti
      </button>
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
        <article class="card scroll-mt-24" id={`post-${f.id}`}>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <WalletChip address={f.handle} label={f.author_name} size={30} />
              <div>
                <p class="text-sm font-medium">{f.author_name}</p>
                <p class="text-xs muted">
                  {relativeTime(f.created_at)} · <span class="text-secondary">{f.topic}</span>
                </p>
              </div>
              {#if user && f.author_id !== user.id}
                <button
                  class="btn-pill !py-0.5 text-xs"
                  class:!border-primary={followingIds.includes(f.author_id)}
                  class:!text-primary={followingIds.includes(f.author_id)}
                  on:click={() => toggleFollow(f.author_id)}
                >
                  {followingIds.includes(f.author_id) ? "Mengikuti" : "Ikuti"}
                </button>
              {/if}
            </div>
          </div>
            <!-- eslint-disable-next-line svelte/no-at-html-tags -->
            <p class="mt-3 text-sm">{@html renderBody(f.body)}</p>
          <div class="mt-3 flex items-center gap-4 border-t pt-3 text-xs muted">
            <button
              class="inline-flex items-center gap-1.5 transition-colors hover:text-tertiary"
              class:text-tertiary={f.liked_by_me}
              aria-pressed={f.liked_by_me}
              on:click={() => toggleLike(f)}
            >
              <Icon name="heart" set={f.liked_by_me ? "solid" : "regular"} size="12px" />
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
              on:click={() => sharePost(f.id)}
            >
              <Icon name="share-nodes" size="12px" />
              {copiedId === f.id ? "Tersalin!" : "Bagikan"}
            </button>
            <button
              class="inline-flex items-center gap-1.5 hover:text-tertiary"
              on:click={() => reportTarget("post", f.id)}
            >
              <Icon name="flag" size="12px" />
              Laporkan
            </button>
          </div>

          {#if openComments.has(f.id)}
            <div class="mt-3 space-y-3 border-t pt-3">
              {#each f.comments ?? [] as c (c.id)}
                <div class="flex items-start gap-2 text-sm">
                  <Icon name="user" size="11px" class="mt-1 muted" />
                   <div class="flex-1">
                     <p>
                       <span class="font-medium">{c.author_name}</span>
                       <span class="text-xs muted"> · {relativeTime(c.created_at)}</span>
                       {#if c.edited_at}<span class="text-xs muted"> · disunting</span>{/if}
                       {#if c.parent_id}<span class="text-xs muted"> · balasan</span>{/if}
                     </p>
                     <!-- eslint-disable-next-line svelte/no-at-html-tags -->
                     <p class="text-ink2">{@html renderBody(c.body)}</p>
                   </div>
                   <div class="flex flex-none items-center gap-1">
                     <button
                       class="btn-icon"
                       on:click={() => replyTo(f, c.id)}
                       aria-label="Balas komentar"
                     >
                       <Icon name="reply" size="10px" />
                     </button>
                     {#if user && (c.author_id === user.id || user.roles?.includes("admin"))}
                       <button
                         class="btn-icon"
                         on:click={() => editComment(f, c)}
                         aria-label="Ubah komentar"
                       >
                         <Icon name="pen" size="10px" />
                       </button>
                       <button
                         class="btn-icon !text-tertiary hover:!border-tertiary"
                         on:click={() => deleteComment(f, c)}
                         disabled={busy === `cd-${c.id}`}
                         aria-label="Hapus komentar"
                       >
                         <Icon name="trash" size="10px" />
                       </button>
                     {:else}
                       <button
                         class="btn-icon"
                         on:click={() => reportTarget("comment", c.id)}
                         aria-label="Laporkan komentar"
                       >
                         <Icon name="flag" size="10px" />
                       </button>
                     {/if}
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
