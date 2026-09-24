<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Notification } from "$lib/types";
  import { notifications } from "$lib/stores/notifications";
  import { relativeTime } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";

  const PAGE = 20;
  let items: Notification[] = [];
  let loading = true;
  let error = "";
  let page = 1;
  let hasMore = false;
  let markingAll = false;
  let markingId = "";

  const iconFor: Record<string, { name: string; klass: string }> = {
    reward: { name: "gem", klass: "text-highlight" },
    quest: { name: "trophy", klass: "text-primary" },
    badge: { name: "medal", klass: "text-secondary" },
    room: { name: "bullseye", klass: "text-tertiary" },
    system: { name: "bell", klass: "text-primary" },
    level: { name: "arrow-up", klass: "text-highlight" },
  };

  const kindLabel: Record<string, string> = {
    reward: "Hadiah",
    quest: "Quest",
    badge: "Badge",
    room: "Ruang",
    system: "Sistem",
    level: "Naik level",
  };
  let mutedKinds: string[] = [];
  let prefsLoading = true;
  let prefsError = "";

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

  async function load() {
    loading = true;
    error = "";
    try {
      items = await api.get<Notification[]>(
        `/notifications?limit=${PAGE}&offset=${(page - 1) * PAGE}`,
      );
      hasMore = items.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat notifikasi";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    page = next;
    load();
  }

  async function markAll() {
    if (markingAll) return;
    error = "";
    markingAll = true;
    try {
      await api.post("/notifications/read-all");
      notifications.clear();
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menandai semua dibaca";
    } finally {
      markingAll = false;
    }
  }

  async function markOne(n: Notification) {
    if (n.read_at || markingId === n.id) return;
    error = "";
    markingId = n.id;
    try {
      await api.post(`/notifications/${n.id}/read`);
      const readAt = new Date().toISOString();
      // Reassign so Svelte reactivity fires for the unread dot.
      items = items.map((x) => (x.id === n.id ? { ...x, read_at: readAt } : x));
      await notifications.refresh();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menandai notifikasi";
    } finally {
      markingId = "";
    }
  }

  onMount(() => {
    load();
    loadPreferences();
  });
</script>

<svelte:head><title>Notifikasi — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <div class="flex items-center justify-between">
    <div>
      <p class="mono-label">Aktivitas</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Notifikasi</h1>
    </div>
    <button class="btn-ghost" on:click={markAll} disabled={markingAll}>
      <Icon name="check-double" size="12px" />
      {markingAll ? "Menandai…" : "Tandai semua dibaca"}
    </button>
  </div>

  {#if error}
    <p class="alert-error mt-6">{error}</p>
  {/if}

  <div class="card mt-6">
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
          >
            <Icon name={mutedKinds.includes(kind) ? "bell-slash" : "bell"} size="10px" />
            {kindLabel[kind]}
          </button>
        {/each}
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="mt-6 space-y-2">
      {#each Array(3) as _}<div class="skeleton h-20 w-full"></div>{/each}
    </div>
  {:else if items.length === 0}
    <div class="card mt-6 grid place-items-center py-14 text-center">
      <Icon name="bell-slash" size="26px" class="muted" />
      <p class="mt-3 font-semibold">Belum ada notifikasi</p>
      <p class="text-sm muted">Kabar tentang hadiah, quest, dan badge akan muncul di sini.</p>
    </div>
  {:else}
    <ul class="mt-6 space-y-2">
      {#each items as n}
        {@const meta = iconFor[n.kind] ?? iconFor.system}
        <li class="card !p-0">
          <button
            type="button"
            class="flex w-full items-start gap-3 p-5 text-left"
            class:opacity-60={n.read_at}
            disabled={markingId === n.id}
            on:click={() => markOne(n)}
          >
            <span class="tile-neutral h-9 w-9">
              <Icon name={meta.name} size="14px" class={meta.klass} />
            </span>
            <span class="flex-1">
              <span class="flex items-center justify-between">
                <span class="font-medium">{n.title}</span>
                <span class="text-xs muted">{relativeTime(n.created_at)}</span>
              </span>
              {#if n.body}<span class="block text-sm muted">{n.body}</span>{/if}
            </span>
            {#if !n.read_at}
              <span class="mt-1 h-2 w-2 flex-none rounded-sm bg-primary"></span>
            {/if}
          </button>
        </li>
      {/each}
    </ul>
    <Pagination
      {page}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="notifikasi"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {/if}
</div>
