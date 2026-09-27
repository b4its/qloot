<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Notification, NotificationPage } from "$lib/types";
  import { notifications } from "$lib/stores/notifications";
  import { relativeTime } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import { reveal } from "$lib/actions/reveal";

  const PAGE = 20;

  let items: Notification[] = [];
  let total = 0;
  let unread = 0;
  let kindCounts: Record<string, number> = {};
  let loading = true;
  let error = "";
  let page = 1;
  let busy = false;

  // Filters
  let query = "";
  let activeKind: string = "all";
  let readFilter: "all" | "unread" | "read" = "all";
  let sortBy: "recent" | "oldest" = "recent";

  // Selection for bulk actions
  let selected = new Set<string>();

  // Notification preferences (mute toggles)
  const kindLabel: Record<string, string> = {
    reward: "Hadiah",
    quest: "Quest",
    badge: "Badge",
    room: "Ruang",
    system: "Sistem",
    level: "Naik level",
    community: "Komunitas",
  };
  const iconFor: Record<string, { name: string; klass: string }> = {
    reward: { name: "gem", klass: "text-highlight" },
    quest: { name: "trophy", klass: "text-primary" },
    badge: { name: "medal", klass: "text-secondary" },
    room: { name: "bullseye", klass: "text-tertiary" },
    system: { name: "bell", klass: "text-primary" },
    level: { name: "arrow-up", klass: "text-highlight" },
    community: { name: "comments", klass: "text-secondary" },
  };
  let mutedKinds: string[] = [];
  let prefsLoading = true;
  let prefsError = "";
  let showPrefs = false;

  async function loadPreferences() {
    prefsLoading = true;
    try {
      const res = await api.get<{ muted_kinds: string[] }>("/notifications/preferences");
      mutedKinds = res.muted_kinds ?? [];
    } catch (e) {
      prefsError = e instanceof ApiError ? e.message : "Gagal memuat preferensi";
    } finally {
      prefsLoading = false;
    }
  }

  async function toggleMute(kind: string) {
    const next = mutedKinds.includes(kind)
      ? mutedKinds.filter((k) => k !== kind)
      : [...mutedKinds, kind];
    prefsError = "";
    try {
      await api.put("/notifications/preferences", { muted_kinds: next });
      mutedKinds = next;
    } catch (e) {
      prefsError = e instanceof ApiError ? e.message : "Gagal menyimpan preferensi";
    }
  }

  function buildQuery(): string {
    const params = new URLSearchParams();
    params.set("limit", String(PAGE));
    params.set("offset", String((page - 1) * PAGE));
    if (activeKind !== "all") params.set("kind", activeKind);
    if (readFilter === "unread") params.set("unread_only", "true");
    if (readFilter === "read") params.set("read_only", "true");
    if (sortBy === "oldest") params.set("oldest_first", "true");
    if (query.trim()) params.set("q", query.trim());
    return params.toString();
  }

  async function load() {
    loading = true;
    error = "";
    try {
      const res = await api.get<NotificationPage>(`/notifications/page?${buildQuery()}`);
      items = res.items ?? [];
      total = res.total ?? items.length;
      unread = res.unread ?? 0;
      kindCounts = res.kind_counts ?? {};
      // Drop selection entries that fell off the page.
      const visible = new Set(items.map((n) => n.id));
      selected = new Set([...selected].filter((id) => visible.has(id)));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat notifikasi";
    } finally {
      loading = false;
    }
  }

  // Re-query the server whenever a filter, search term, or sort changes.
  let debounce: ReturnType<typeof setTimeout> | null = null;
  function refilter() {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => {
      page = 1;
      void load();
    }, 200);
  }

  function setKind(kind: string) {
    if (activeKind === kind) return;
    activeKind = kind;
    refilter();
  }

  function setReadFilter(val: "all" | "unread" | "read") {
    if (readFilter === val) return;
    readFilter = val;
    refilter();
  }

  function onSearchInput() {
    refilter();
  }

  function onSortChange() {
    // Sort is now server-backed via `oldest_first`, so pagination stays
    // consistent across pages instead of only reordering the current page.
    refilter();
  }

  function go(delta: number) {
    const next = page + delta;
    const totalPages = Math.max(1, Math.ceil(total / PAGE));
    if (next < 1 || next > totalPages) return;
    page = next;
    void load();
  }

  $: totalPages = Math.max(1, Math.ceil(total / PAGE));
  $: hasMore = page < totalPages;

  async function markAll() {
    if (busy || unread === 0) return;
    error = "";
    busy = true;
    try {
      await api.post("/notifications/read-all");
      notifications.clear();
      selected = new Set();
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menandai semua dibaca";
    } finally {
      busy = false;
    }
  }

  async function markOne(n: Notification) {
    if (n.read_at || busy) return;
    error = "";
    try {
      await api.post(`/notifications/${n.id}/read`);
      const readAt = new Date().toISOString();
      items = items.map((x) => (x.id === n.id ? { ...x, read_at: readAt } : x));
      unread = Math.max(0, unread - 1);
      await notifications.refresh();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menandai notifikasi";
    }
  }

  async function markSelected() {
    if (busy || selected.size === 0) return;
    error = "";
    busy = true;
    try {
      await api.post("/notifications/read-batch", { ids: [...selected] });
      selected = new Set();
      await notifications.refresh();
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menandai notifikasi";
    } finally {
      busy = false;
    }
  }

  async function remove(n: Notification) {
    if (busy) return;
    error = "";
    busy = true;
    try {
      await api.delete(`/notifications/${n.id}`);
      selected.delete(n.id);
      selected = new Set(selected);
      await notifications.refresh();
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus notifikasi";
    } finally {
      busy = false;
    }
  }

  async function clearRead() {
    if (busy) return;
    error = "";
    busy = true;
    try {
      await api.post("/notifications/clear-read");
      selected = new Set();
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membersihkan notifikasi";
    } finally {
      busy = false;
    }
  }

  function toggleSelect(id: string) {
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    selected = new Set(selected);
  }

  $: allVisibleSelected = items.length > 0 && items.every((n) => selected.has(n.id));
  function toggleSelectAll() {
    selected = allVisibleSelected ? new Set() : new Set(items.map((n) => n.id));
  }

  /** Defensive in-page ordering; the server already sorts by recency. */
  $: visibleItems = [...items].sort((a, b) => {
    const ta = new Date(a.created_at).getTime();
    const tb = new Date(b.created_at).getTime();
    return sortBy === "recent" ? tb - ta : ta - tb;
  });

  $: readCount = Math.max(0, total - unread);
  $: readPct = total > 0 ? Math.round((readCount / total) * 100) : 0;

  /** Resolve a notification's context into an in-app deep link, when known. */
  function linkFor(n: Notification): string | null {
    const d = (n.data ?? {}) as Record<string, unknown>;
    const id = (key: string) => (typeof d[key] === "string" ? (d[key] as string) : null);
    switch (n.kind) {
      case "reward":
        if (id("quest_id")) return "/quests";
        if (id("attempt_id")) return "/exams";
        return "/wallet";
      case "quest":
        return "/quests";
      case "badge":
        return "/badges";
      case "room":
        return id("room_id") ? `/rooms/${id("room_id")}` : "/rooms";
      case "level":
        return "/ranking";
      case "community":
        return "/community";
      default:
        return null;
    }
  }

  async function open(n: Notification) {
    await markOne(n);
    const href = linkFor(n);
    if (href) await goto(href);
  }

  onMount(() => {
    void load();
    void loadPreferences();
  });
</script>

<svelte:head><title>Notifikasi — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Aktivitas</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Notifikasi</h1>
      <p class="mt-2 max-w-2xl muted">
        Kabar tentang hadiah, quest, badge, dan komunitasmu. Klik notifikasi untuk membuka
        konteksnya, atau pilih beberapa untuk tindakan massal.
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button class="btn-ghost !py-1.5" on:click={() => (showPrefs = !showPrefs)}>
        <Icon name="sliders" size="12px" />
        {showPrefs ? "Sembunyikan preferensi" : "Preferensi"}
      </button>
      <button
        class="btn-ghost !py-1.5"
        on:click={markAll}
        disabled={busy || unread === 0}
        data-role="mark-all"
      >
        <Icon name="check-double" size="12px" />
        Tandai semua dibaca
      </button>
    </div>
  </div>

  {#if error}
    <p class="alert-error mt-4">{error}</p>
  {/if}

  <!-- Overview metrics -->
  <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
    <div class="card p-4">
      <p class="mono-label text-[10px]">Total</p>
      <p class="mt-1 font-display text-3xl font-bold">{total}</p>
    </div>
    <div class="card p-4">
      <p class="mono-label text-[10px]">Belum dibaca</p>
      <p class="mt-1 font-display text-3xl font-bold text-highlight" data-role="unread">
        {unread}
      </p>
    </div>
    <div class="card p-4">
      <p class="mono-label text-[10px]">Sudah dibaca</p>
      <p class="mt-1 font-display text-3xl font-bold text-mint">{readCount}</p>
    </div>
    <div class="card p-4">
      <p class="mono-label text-[10px]">Rasio dibaca</p>
      <p class="mt-1 font-display text-3xl font-bold">{readPct}%</p>
    </div>
  </div>

  {#if showPrefs}
    <div class="card mt-4">
      <p class="mono-label">Preferensi</p>
      <h2 class="mt-1 font-display text-lg font-bold">Jenis notifikasi</h2>
      <p class="mt-1 text-sm muted">Matikan jenis notifikasi yang tidak ingin kamu terima.</p>
      {#if prefsError}
        <p class="alert-error mt-2 text-xs">{prefsError}</p>
      {/if}
      {#if !prefsLoading}
        <div class="mt-3 flex flex-wrap gap-2">
          {#each Object.keys(kindLabel) as kind}
            <button
              type="button"
              class="badge"
              class:badge-neutral={mutedKinds.includes(kind)}
              class:badge-mint={!mutedKinds.includes(kind)}
              on:click={() => toggleMute(kind)}
              aria-pressed={mutedKinds.includes(kind)}
            >
              <Icon name={mutedKinds.includes(kind) ? "bell-slash" : "bell"} size="10px" />
              {kindLabel[kind]}
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  <!-- Search & filters -->
  <div class="mt-6 flex flex-wrap items-center gap-2">
    <div class="relative w-full sm:w-64">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-9 w-full"
        placeholder="Cari notifikasi..."
        bind:value={query}
        on:input={onSearchInput}
        aria-label="Cari notifikasi"
      />
      {#if query}
        <button
          type="button"
          class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
          on:click={() => (query = "")}
          aria-label="Bersihkan pencarian"
        >
          ✕
        </button>
      {/if}
    </div>

    <div class="flex items-center gap-1 rounded-sm border p-1 surface text-xs">
      {#each [["all", "Semua"], ["unread", "Belum dibaca"], ["read", "Dibaca"]] as [val, label]}
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={readFilter === val}
          class:text-[#05060A]={readFilter === val}
          class:muted={readFilter !== val}
          on:click={() => setReadFilter(val as typeof readFilter)}
        >
          {label}
        </button>
      {/each}
    </div>

    <select
      class="input text-xs !py-1.5 w-auto"
      bind:value={sortBy}
      on:change={onSortChange}
      aria-label="Urutkan"
    >
      <option value="recent">Terbaru dulu</option>
      <option value="oldest">Terlama dulu</option>
    </select>

    {#if readCount > 0}
      <button class="btn-ghost !py-1.5 text-xs" on:click={clearRead} disabled={busy}>
        <Icon name="broom" size="11px" /> Bersihkan yang dibaca
      </button>
    {/if}
  </div>

  <!-- Kind chips with per-kind counts -->
  {#if Object.keys(kindCounts).length > 0}
    <div class="mt-3 flex flex-wrap gap-1.5">
      <button
        type="button"
        class="badge"
        class:badge-mint={activeKind === "all"}
        class:badge-neutral={activeKind !== "all"}
        on:click={() => setKind("all")}
      >
        Semua ({total})
      </button>
      {#each Object.entries(kindCounts) as [kind, count]}
        <button
          type="button"
          class="badge"
          class:badge-mint={activeKind === kind}
          class:badge-neutral={activeKind !== kind}
          on:click={() => setKind(kind)}
        >
          {kindLabel[kind] ?? kind} ({count})
        </button>
      {/each}
    </div>
  {/if}

  <!-- Bulk action bar -->
  {#if items.length > 0}
    <div
      class="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-sm border p-3 surface text-xs"
    >
      <label class="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={allVisibleSelected}
          on:change={toggleSelectAll}
          aria-label="Pilih semua di halaman ini"
        />
        <span class="muted">{selected.size > 0 ? `${selected.size} dipilih` : "Pilih semua"}</span>
      </label>
      {#if selected.size > 0}
        <div class="flex items-center gap-2">
          <button class="btn-ghost !py-1 text-xs" on:click={markSelected} disabled={busy}>
            <Icon name="check" size="11px" /> Tandai dibaca
          </button>
          <button class="btn-ghost !py-1 text-xs" on:click={() => (selected = new Set())}>
            Batalkan pilihan
          </button>
        </div>
      {/if}
    </div>
  {/if}

  {#if loading}
    <div class="mt-4 space-y-2">
      {#each Array(4) as _}<div class="skeleton h-20 w-full"></div>{/each}
    </div>
  {:else if items.length === 0}
    <div class="card mt-6 grid place-items-center py-14 text-center">
      <Icon name="bell-slash" size="26px" class="muted" />
      <p class="mt-3 font-semibold">
        {query || activeKind !== "all" || readFilter !== "all"
          ? "Tidak ada notifikasi yang cocok"
          : "Belum ada notifikasi"}
      </p>
      <p class="text-sm muted">
        {query || activeKind !== "all" || readFilter !== "all"
          ? "Coba ubah pencarian atau filter."
          : "Kabar tentang hadiah, quest, dan badge akan muncul di sini."}
      </p>
    </div>
  {:else}
    <ul class="mt-4 space-y-2">
      {#each visibleItems as n, i (n.id)}
        {@const meta = iconFor[n.kind] ?? iconFor.system}
        {@const href = linkFor(n)}
        <li use:reveal={{ delay: i * 15 }} class="card !p-0" data-notification={n.id}>
          <div class="flex items-start gap-3 p-4" class:opacity-60={n.read_at}>
            <input
              type="checkbox"
              class="mt-1"
              checked={selected.has(n.id)}
              on:change={() => toggleSelect(n.id)}
              aria-label={`Pilih ${n.title}`}
            />
            <button
              type="button"
              class="flex flex-1 items-start gap-3 text-left"
              on:click={() => open(n)}
              title={href ? "Buka" : undefined}
            >
              <span class="tile-neutral h-9 w-9 flex-none">
                <Icon name={meta.name} size="14px" class={meta.klass} />
              </span>
              <span class="flex-1">
                <span class="flex items-center justify-between gap-2">
                  <span class="font-medium" class:font-bold={!n.read_at}>{n.title}</span>
                  <span class="flex-none text-xs muted">{relativeTime(n.created_at)}</span>
                </span>
                {#if n.body}<span class="mt-0.5 block text-sm muted">{n.body}</span>{/if}
                <span class="mt-1 flex items-center gap-2">
                  <span class="badge badge-neutral text-[10px]">
                    {kindLabel[n.kind] ?? n.kind}
                  </span>
                  {#if href}
                    <span class="text-[10px] muted"
                      ><Icon name="arrow-right" size="9px" /> buka</span
                    >
                  {/if}
                </span>
              </span>
            </button>
            <div class="flex flex-none flex-col items-center gap-2">
              {#if !n.read_at}
                <span
                  class="h-2 w-2 rounded-sm bg-primary"
                  aria-label="Belum dibaca"
                  data-role="unread-dot"
                ></span>
              {/if}
              <button
                type="button"
                class="text-muted hover:text-danger text-xs"
                on:click={() => remove(n)}
                disabled={busy}
                aria-label={`Hapus ${n.title}`}
                data-role="delete"
              >
                <Icon name="trash" size="11px" />
              </button>
            </div>
          </div>
        </li>
      {/each}
    </ul>
    <Pagination
      {page}
      pageSize={PAGE}
      {total}
      {loading}
      label="notifikasi"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {/if}
</div>
