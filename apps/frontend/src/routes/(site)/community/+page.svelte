<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";
  import { api, ApiError } from "$lib/api/client";
  import { auth } from "$lib/stores/auth";
  import { relativeTime } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import Dialog from "$lib/components/Dialog.svelte";

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
  // COMM: free-text search over post body / author name.
  let query = "";
  // COMM-06: restrict the feed to authors the viewer follows.
  let followingOnly = false;
  let followingIds: string[] = [];
  let followingLoaded = true;
  let openComments = new Set<string>();
  let commentDraft: Record<string, string> = {};
  let busy = "";
  let page = 1;
  let hasMore = false;
  /** Post id whose share link was just copied (shows a transient "Tersalin"). */
  let copiedId = "";

  interface UserLevelCard {
    xp: number;
    level: number;
    progress: number;
    quest_wins: number;
    tasks_completed: number;
    breakdown: { exams: number; quests: number; tasks: number; badges: number };
  }
  let inspectingUser: { id: string; name: string } | null = null;
  let inspectingLevel: UserLevelCard | null = null;
  let inspectingLoading = false;
  let inspectingError = "";

  async function inspectUserLevel(id: string, name: string) {
    inspectingUser = { id, name };
    inspectingLoading = true;
    inspectingLevel = null;
    inspectingError = "";
    try {
      inspectingLevel = await api.get<UserLevelCard>(`/gamification/levels/${id}`);
    } catch (e) {
      inspectingError =
        e instanceof ApiError ? e.message : "Gagal memuat data gamifikasi pengguna.";
    } finally {
      inspectingLoading = false;
    }
  }

  function closeInspectUserLevel() {
    inspectingUser = null;
    inspectingLevel = null;
    inspectingError = "";
  }

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
      if (query.trim()) params.set("q", query.trim());
      [posts, topics, stats] = await Promise.all([
        api.get<Post[]>(`/community/posts?${params.toString()}`),
        api.get<Topic[]>("/community/topics"),
        api.get<typeof stats>("/community/stats"),
      ]);
      if (user) {
        // If this fails we must not present every author as "Ikuti" (which would
        // be wrong for already-followed authors) — mark the list as unavailable.
        try {
          followingIds = await api.get<string[]>("/me/following");
          followingLoaded = true;
        } catch {
          followingIds = [];
          followingLoaded = false;
        }
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

  // Debounced search so typing filters the feed without hammering the API.
  let searchDebounce: ReturnType<typeof setTimeout> | null = null;
  function onSearch() {
    if (searchDebounce) clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      page = 1;
      openComments = new Set();
      void load();
    }, 300);
  }

  function clearSearch() {
    query = "";
    page = 1;
    void load();
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
    const escaped = (body ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return escaped.replace(
      /@([A-Za-z0-9_.\- ]{2,64}?)(?=[,.!?;:\n]|$)/g,
      (_m, name) =>
        `<a class="text-primary hover:underline" href="/community?mention=${encodeURIComponent(
          name.trim(),
        )}">@${name.trim()}</a>`,
    );
  }

  const REPORT_REASONS = [
    "Spam atau promosi tidak relevan",
    "Pelecehan, ujaran kebencian, atau SARA",
    "Konten tidak pantas atau menyesatkan",
    "Pelanggaran hak cipta atau plagiarisme",
    "Lainnya",
  ];

  let reportingTarget: { type: "post" | "comment"; id: string } | null = null;
  let deletingComment: { post: Post; comment: Comment } | null = null;
  let deletingPost: Post | null = null;
  let reportCategory = REPORT_REASONS[0];
  let reportCustomDetail = "";
  let reportNotice = "";
  let reportingBusy = false;

  let activeReplyTarget: { post: Post; parentCommentId: string } | null = null;
  let replyDraft = "";
  let replyingBusy = false;

  let activeEditTarget: { post: Post; comment: Comment } | null = null;
  let editDraft = "";
  let editingBusy = false;

  /** COMM-02: reply to a specific comment (nested). */
  function replyTo(p: Post, parentId: string) {
    activeReplyTarget = { post: p, parentCommentId: parentId };
    replyDraft = "";
  }

  async function submitReply() {
    if (!activeReplyTarget || !replyDraft.trim() || replyingBusy) return;
    replyingBusy = true;
    error = "";
    try {
      await api.post(`/community/posts/${activeReplyTarget.post.id}/comments`, {
        body: replyDraft.trim(),
        parent_id: activeReplyTarget.parentCommentId,
      });
      await loadComments(activeReplyTarget.post);
      activeReplyTarget.post.comment_count += 1;
      posts = posts.map((x) => (x.id === activeReplyTarget!.post.id ? activeReplyTarget!.post : x));
      activeReplyTarget = null;
      replyDraft = "";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membalas";
    } finally {
      replyingBusy = false;
    }
  }

  /** COMM-02: edit your own comment. */
  function editComment(p: Post, c: Comment) {
    activeEditTarget = { post: p, comment: c };
    editDraft = c.body;
  }

  async function submitEdit() {
    if (!activeEditTarget || !editDraft.trim() || editingBusy) return;
    if (editDraft.trim() === activeEditTarget.comment.body) {
      activeEditTarget = null;
      return;
    }
    editingBusy = true;
    error = "";
    try {
      await api.patch(`/community/comments/${activeEditTarget.comment.id}`, {
        body: editDraft.trim(),
      });
      await loadComments(activeEditTarget.post);
      activeEditTarget = null;
      editDraft = "";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah komentar";
    } finally {
      editingBusy = false;
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
  function reportTarget(targetType: "post" | "comment", targetId: string) {
    reportingTarget = { type: targetType, id: targetId };
    reportCategory = REPORT_REASONS[0];
    reportCustomDetail = "";
  }

  // True when "Lainnya" is chosen but the free-text detail is too short to submit.
  $: reportReasonTooShort = reportCategory === "Lainnya" && reportCustomDetail.trim().length < 3;

  async function submitReport() {
    if (!reportingTarget || reportingBusy || reportReasonTooShort) return;
    const finalReason =
      reportCategory === "Lainnya"
        ? reportCustomDetail.trim()
        : reportCustomDetail.trim()
          ? `${reportCategory}: ${reportCustomDetail.trim()}`
          : reportCategory;

    if (finalReason.length < 3) return;

    reportingBusy = true;
    error = "";
    try {
      await api.post("/community/reports", {
        target_type: reportingTarget.type,
        target_id: reportingTarget.id,
        reason: finalReason,
      });
      // Success feedback is surfaced via `reportNotice` below.
      reportNotice = "Laporan berhasil dikirim ke tim moderator untuk ditinjau.";
      setTimeout(() => {
        reportNotice = "";
      }, 4000);
      reportingTarget = null;
      reportCustomDetail = "";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal melaporkan konten";
    } finally {
      reportingBusy = false;
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
    deletingComment = { post: p, comment: c };
  }

  async function confirmDeleteComment() {
    const target = deletingComment;
    if (!target) return;
    deletingComment = null;
    const { post: p, comment: c } = target;
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

  /** Delete your own post (or any, as an admin). */
  function deletePost(p: Post) {
    deletingPost = p;
  }

  async function confirmDeletePost() {
    const p = deletingPost;
    if (!p) return;
    deletingPost = null;
    busy = `pd-${p.id}`;
    try {
      await api.delete(`/community/posts/${p.id}`);
      posts = posts.filter((x) => x.id !== p.id);
      reportNotice = "Diskusi dihapus.";
      setTimeout(() => (reportNotice = ""), 4000);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus diskusi";
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

    <!-- Search -->
    <div class="relative">
      <Icon
        name="magnifying-glass"
        size="13px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input !pl-9"
        placeholder="Cari diskusi atau nama penulis…"
        bind:value={query}
        on:input={onSearch}
        aria-label="Cari diskusi"
      />
      {#if query}
        <button
          type="button"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
          on:click={clearSearch}
          aria-label="Bersihkan pencarian"
        >
          ✕
        </button>
      {/if}
      {#if query && !loading}
        <p class="mt-1 text-xs muted" data-role="search-count" role="status" aria-live="polite">
          {posts.length} hasil untuk "{query}"
        </p>
      {/if}
    </div>

    {#if reportNotice}
      <div
        class="alert-ok flex items-center justify-between text-xs"
        role="status"
        aria-live="polite"
      >
        <span class="flex items-center gap-1.5"
          ><Icon name="circle-check" size="14px" /> {reportNotice}</span
        >
        <button
          class="text-xs text-muted hover:text-foreground"
          on:click={() => (reportNotice = "")}
          aria-label="Tutup notifikasi">✕</button
        >
      </div>
    {/if}

    {#if error}
      <p class="alert-error" role="alert" aria-live="assertive">{error}</p>
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
      <EmptyState
        icon="comments"
        title="Belum ada diskusi"
        description="Jadilah yang pertama memulai percakapan."
      />
    {:else}
      {#each posts as f (f.id)}
        <article class="card scroll-mt-24" id={`post-${f.id}`}>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <WalletChip address={f.handle} label={f.author_name} size={30} />
              <div>
                <button
                  type="button"
                  class="text-sm font-medium hover:text-primary transition-colors text-left flex items-center gap-1.5"
                  on:click={() => inspectUserLevel(f.author_id, f.author_name)}
                  title="Lihat level & statistik pengguna"
                >
                  <span>{f.author_name}</span>
                  <Icon name="medal" size="10px" class="text-secondary" />
                </button>
                <p class="text-xs muted">
                  {relativeTime(f.created_at)} · <span class="text-secondary">{f.topic}</span>
                </p>
              </div>
              {#if user && f.author_id !== user.id}
                <button
                  class="btn-pill !py-0.5 text-xs"
                  class:!border-primary={followingLoaded && followingIds.includes(f.author_id)}
                  class:!text-primary={followingLoaded && followingIds.includes(f.author_id)}
                  on:click={() => toggleFollow(f.author_id)}
                  disabled={!followingLoaded}
                  title={followingLoaded ? undefined : "Status ikutan belum tersedia"}
                >
                  {followingLoaded
                    ? followingIds.includes(f.author_id)
                      ? "Mengikuti"
                      : "Ikuti"
                    : "Ikuti —"}
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
            {#if user && (f.author_id === user.id || user.roles?.includes("admin"))}
              <button
                class="inline-flex items-center gap-1.5 transition-colors hover:text-danger"
                on:click={() => deletePost(f)}
                disabled={busy === `pd-${f.id}`}
                aria-label="Hapus diskusi"
              >
                <Icon name="trash" size="12px" />
                Hapus
              </button>
            {/if}
          </div>

          {#if openComments.has(f.id)}
            <div class="mt-3 space-y-3 border-t pt-3">
              {#each f.comments ?? [] as c (c.id)}
                <div class="flex items-start gap-2 text-sm">
                  <Icon name="user" size="11px" class="mt-1 muted" />
                  <div class="flex-1">
                    <p>
                      <button
                        type="button"
                        class="font-medium hover:text-primary transition-colors text-left"
                        on:click={() => inspectUserLevel(c.author_id, c.author_name)}
                        title="Lihat level pengguna"
                      >
                        {c.author_name}
                      </button>
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

{#if inspectingUser}
  <Dialog
    title={inspectingUser.name}
    description="Profil gamifikasi pengguna"
    size="max-w-sm"
    close={closeInspectUserLevel}
  >
    {#if inspectingLoading}
      <div class="skeleton h-24"></div>
    {:else if inspectingLevel}
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <span class="mono-label">Level</span>
            <p class="font-display text-3xl font-extrabold text-primary">
              Lv. {inspectingLevel.level}
            </p>
          </div>
          <div class="text-right">
            <span class="mono-label">Total XP</span>
            <p class="font-mono text-xl font-bold">
              {inspectingLevel.xp.toLocaleString("id-ID")} XP
            </p>
          </div>
        </div>

        <div>
          <div class="flex justify-between text-xs muted mb-1">
            <span>Progres Level</span>
            <span>{Math.round(inspectingLevel.progress * 100)}%</span>
          </div>
          <div
            class="h-2 w-full overflow-hidden rounded-full bg-surface-2"
            role="progressbar"
            aria-valuenow={Math.round(inspectingLevel.progress * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Progres level"
          >
            <div
              class="h-full bg-primary"
              style="width: {Math.round(inspectingLevel.progress * 100)}%"
            ></div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-2 border-t pt-3 text-xs">
          <div class="card !p-2">
            <span class="mono-label">Ujian</span>
            <p class="font-semibold">{inspectingLevel.breakdown?.exams ?? 0} XP</p>
          </div>
          <div class="card !p-2">
            <span class="mono-label">Quest</span>
            <p class="font-semibold">{inspectingLevel.breakdown?.quests ?? 0} XP</p>
          </div>
          <div class="card !p-2">
            <span class="mono-label">Tugas</span>
            <p class="font-semibold">{inspectingLevel.breakdown?.tasks ?? 0} XP</p>
          </div>
          <div class="card !p-2">
            <span class="mono-label">Badge</span>
            <p class="font-semibold">{inspectingLevel.breakdown?.badges ?? 0} XP</p>
          </div>
        </div>

        {#if inspectingLevel.quest_wins > 0}
          <p class="text-xs text-mint">🏆 Memenangkan {inspectingLevel.quest_wins} quest</p>
        {/if}
      </div>
    {:else if inspectingError}
      <p class="py-4 text-center text-xs text-danger" role="alert">{inspectingError}</p>
    {:else}
      <p class="py-4 text-center text-xs muted">Data gamifikasi pengguna tidak tersedia.</p>
    {/if}
    <svelte:fragment slot="footer">
      <div class="flex justify-end">
        <button class="btn-ghost text-xs" on:click={closeInspectUserLevel}>Tutup</button>
      </div>
    </svelte:fragment>
  </Dialog>
{/if}

{#if reportingTarget}
  <Dialog
    title={`Laporkan ${reportingTarget.type === "post" ? "Diskusi" : "Komentar"}`}
    description="Pilih alasan pelaporan; tim moderator akan meninjau laporanmu."
    size="max-w-md"
    busy={reportingBusy}
    close={() => (reportingTarget = null)}
  >
    <div class="space-y-3">
      <fieldset>
        <legend class="block text-xs font-medium">Pilih Alasan Pelaporan</legend>
        <div class="mt-2 space-y-2">
          {#each REPORT_REASONS as reason}
            <label
              class="flex cursor-pointer items-center gap-2 rounded-sm border p-2.5 text-xs transition-colors hover:border-primary/40"
              class:border-primary={reportCategory === reason}
              class:bg-primary-10={reportCategory === reason}
            >
              <input
                type="radio"
                name="report-reason"
                value={reason}
                checked={reportCategory === reason}
                on:change={() => (reportCategory = reason)}
              />
              <span>{reason}</span>
            </label>
          {/each}
        </div>
      </fieldset>

      {#if reportCategory === "Lainnya"}
        <div class="pt-1">
          <label for="report-detail-text" class="mb-1 block text-xs muted"
            >Keterangan Tambahan</label
          >
          <textarea
            id="report-detail-text"
            class="input min-h-[70px] text-xs"
            placeholder="Jelaskan minimal 3 karakter detail pelanggaran..."
            bind:value={reportCustomDetail}
          ></textarea>
          {#if reportCustomDetail.trim().length > 0 && reportCustomDetail.trim().length < 3}
            <p class="mt-1 text-xs text-danger" role="alert">
              Keterangan minimal 3 karakter agar moderator memahami konteksnya.
            </p>
          {/if}
        </div>
      {/if}
    </div>
    <svelte:fragment slot="footer">
      <div class="flex items-center justify-end gap-2">
        <button type="button" class="btn-ghost text-xs" on:click={() => (reportingTarget = null)}
          >Batal</button
        >
        <button
          type="button"
          class="btn-primary !border-magenta !bg-magenta text-xs hover:!bg-magenta/80"
          on:click={submitReport}
          disabled={reportingBusy || reportReasonTooShort}
        >
          {#if reportingBusy}<Icon name="spinner" spin size="12px" />{/if}
          <span>{reportingBusy ? "Mengirim Laporan…" : "Kirim Laporan"}</span>
        </button>
      </div>
    </svelte:fragment>
  </Dialog>
{/if}

{#if activeReplyTarget}
  <Dialog
    title="Tulis Tanggapan Anda"
    description="Balas komentar ini untuk melanjutkan diskusi."
    size="max-w-md"
    busy={replyingBusy}
    close={() => (activeReplyTarget = null)}
  >
    <textarea
      class="input min-h-[100px] text-xs"
      placeholder="Tulis balasan untuk komentar ini..."
      aria-label="Isi balasan"
      bind:value={replyDraft}
      data-autofocus
      on:keydown={(e) => {
        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
          submitReply();
        }
      }}
    ></textarea>
    <svelte:fragment slot="footer">
      <div class="flex items-center justify-end gap-2">
        <button type="button" class="btn-ghost text-xs" on:click={() => (activeReplyTarget = null)}
          >Batal</button
        >
        <button
          type="button"
          class="btn-primary text-xs"
          on:click={submitReply}
          disabled={replyingBusy || !replyDraft.trim()}
        >
          {#if replyingBusy}<Icon name="spinner" spin size="12px" />{/if}
          <span>{replyingBusy ? "Mengirim…" : "Kirim Balasan"}</span>
        </button>
      </div>
    </svelte:fragment>
  </Dialog>
{/if}

{#if activeEditTarget}
  <Dialog
    title="Ubah Isi Komentar"
    description="Perbarui komentar yang sudah kamu tulis."
    size="max-w-md"
    busy={editingBusy}
    close={() => (activeEditTarget = null)}
  >
    <textarea
      class="input min-h-[100px] text-xs"
      placeholder="Ubah komentar Anda..."
      aria-label="Isi komentar"
      bind:value={editDraft}
      data-autofocus
      on:keydown={(e) => {
        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
          submitEdit();
        }
      }}
    ></textarea>
    <svelte:fragment slot="footer">
      <div class="flex items-center justify-end gap-2">
        <button type="button" class="btn-ghost text-xs" on:click={() => (activeEditTarget = null)}
          >Batal</button
        >
        <button
          type="button"
          class="btn-primary text-xs"
          on:click={submitEdit}
          disabled={editingBusy || !editDraft.trim()}
        >
          {#if editingBusy}<Icon name="spinner" spin size="12px" />{/if}
          <span>{editingBusy ? "Menyimpan…" : "Simpan Perubahan"}</span>
        </button>
      </div>
    </svelte:fragment>
  </Dialog>
{/if}

{#if deletingComment}
  <ConfirmDialog
    title="Hapus Komentar"
    description="Komentar ini akan dihapus dari diskusi dan tidak dapat dikembalikan."
    confirmLabel="Ya, Hapus"
    onConfirm={confirmDeleteComment}
    close={() => (deletingComment = null)}
  />
{/if}

{#if deletingPost}
  <ConfirmDialog
    title="Hapus Diskusi"
    description="Diskusi ini beserta komentarnya akan dihapus dan tidak dapat dikembalikan."
    confirmLabel="Ya, Hapus"
    busy={busy === `pd-${deletingPost.id}`}
    onConfirm={confirmDeletePost}
    close={() => (deletingPost = null)}
  />
{/if}
