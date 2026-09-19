<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api/client";
  import type { Notification } from "$lib/types";
  import { notifications } from "$lib/stores/notifications";
  import { relativeTime } from "$lib/utils/format";

  let items: Notification[] = [];
  let loading = true;

  const iconFor: Record<string, string> = {
    reward: "💎",
    quest: "🏆",
    badge: "🏅",
    room: "🎯",
    system: "🔔",
  };

  async function load() {
    loading = true;
    try {
      items = await api.get<Notification[]>("/notifications");
    } finally {
      loading = false;
    }
  }

  async function markAll() {
    await api.post("/notifications/read-all");
    notifications.clear();
    await load();
  }

  async function markOne(n: Notification) {
    if (n.read_at) return;
    await api.post(`/notifications/${n.id}/read`);
    n.read_at = new Date().toISOString();
    await notifications.refresh();
  }

  onMount(load);
</script>

<svelte:head><title>Notifications — QLoot</title></svelte:head>

<div class="flex items-center justify-between">
  <h1 class="text-2xl font-bold">Notifications</h1>
  <button class="btn-ghost" on:click={markAll}>Mark all read</button>
</div>

{#if loading}
  <p class="mt-6 muted">Loading…</p>
{:else if items.length === 0}
  <div class="card mt-6 text-center"><p class="muted">No notifications yet.</p></div>
{:else}
  <ul class="mt-6 space-y-2">
    {#each items as n}
      <li class="card !p-0">
        <button
          type="button"
          class="flex w-full items-start gap-3 p-5 text-left"
          class:opacity-60={n.read_at}
          on:click={() => markOne(n)}
        >
          <span class="text-xl" aria-hidden="true">{iconFor[n.kind] ?? "🔔"}</span>
          <span class="flex-1">
            <span class="flex items-center justify-between">
              <span class="font-medium">{n.title}</span>
              <span class="text-xs muted">{relativeTime(n.created_at)}</span>
            </span>
            {#if n.body}<span class="block text-sm muted">{n.body}</span>{/if}
          </span>
          {#if !n.read_at}
            <span class="mt-1 h-2 w-2 flex-none rounded-full bg-primary-500"></span>
          {/if}
        </button>
      </li>
    {/each}
  </ul>
{/if}
