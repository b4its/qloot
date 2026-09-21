<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { page } from "$app/stores";
  import { api, wsUrl, ApiError } from "$lib/api/client";
  import type { Room, RankingResponse } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";

  let room: Room | null = null;
  let participants: { user_id: string; is_present: boolean; role: string }[] = [];
  let ranking: RankingResponse | null = null;
  let loading = true;
  let error = "";
  let connected = false;
  let events: { text: string; at: number }[] = [];
  let socket: WebSocket | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempts = 0;
  let destroyed = false;
  let busy = "";

  const roomId = $page.params.roomId;
  $: canManage = hasRole($auth.user, "teacher");

  async function load() {
    try {
      room = await api.get<Room>(`/rooms/${roomId}`);
      participants = await api.get(`/rooms/${roomId}/participants`);
      ranking = await api.get<RankingResponse>(`/rankings/rooms/${roomId}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load room";
    } finally {
      loading = false;
    }
  }

  function connect() {
    if (destroyed) return;
    socket?.close();
    socket = new WebSocket(wsUrl(`/api/v1/ws/rooms/${roomId}`));

    socket.onopen = () => {
      connected = true;
      reconnectAttempts = 0;
      pingTimer = setInterval(() => socket?.send(JSON.stringify({ type: "ping" })), 25000);
    };
    socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "pong") return;
        events = [
          {
            text: `${msg.type}${msg.user_id ? ` · ${String(msg.user_id).slice(0, 8)}` : ""}`,
            at: Date.now(),
          },
          ...events,
        ].slice(0, 20);
        // Refresh light state on meaningful events.
        if (
          ["room.join", "room.leave", "room.open", "room.close", "quest.finalized"].includes(
            msg.type,
          )
        ) {
          load();
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    socket.onclose = () => {
      connected = false;
      if (pingTimer) clearInterval(pingTimer);
      if (destroyed) return;
      // Bounded exponential backoff (1s → 30s), stop after ~8 attempts.
      reconnectAttempts += 1;
      if (reconnectAttempts > 8) return;
      const delay = Math.min(30000, 1000 * 2 ** (reconnectAttempts - 1));
      reconnectTimer = setTimeout(connect, delay);
    };
    socket.onerror = () => socket?.close();
  }

  async function act(path: string, key: string) {
    error = "";
    busy = key;
    try {
      await api.post(`/rooms/${roomId}/${path}`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Aksi gagal";
    } finally {
      busy = "";
    }
  }

  async function join() {
    await act("join", "join");
  }
  async function leave() {
    await act("leave", "leave");
  }
  async function openRoom() {
    await act("open", "open");
  }
  async function closeRoom() {
    await act("close", "close");
  }

  onMount(async () => {
    await load();
    connect();
  });

  onDestroy(() => {
    destroyed = true;
    if (pingTimer) clearInterval(pingTimer);
    if (reconnectTimer) clearTimeout(reconnectTimer);
    socket?.close();
  });
</script>

<svelte:head><title>{room?.name ?? "Room"} — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  {#if loading}
    <p class="muted">Loading room…</p>
  {:else if error}
    <p class="alert-error">
      {error}
    </p>
  {:else if room}
    <a href="/rooms" class="text-sm text-primary">← All rooms</a>
    <div class="mt-2 flex flex-wrap items-center gap-3">
      <h1 class="font-display text-3xl font-bold">{room.name}</h1>
      <span
        class="badge"
        class:badge-mint={room.status === "open"}
        class:badge-neutral={room.status !== "open"}
      >
        {room.status}
      </span>
      <span class="badge" class:badge-mint={connected} class:badge-neutral={!connected}>
        {connected ? "● live" : "○ offline"}
      </span>
    </div>
    <p class="mt-1 font-mono text-sm muted">Room code: {room.code}</p>

    <div class="mt-4 flex flex-wrap gap-2">
      <button class="btn-ghost" on:click={join}>Join</button>
      <button class="btn-ghost" on:click={leave}>Leave</button>
      {#if canManage}
        <button class="btn-primary" on:click={openRoom}>Open room</button>
        <button class="btn-ghost" on:click={closeRoom}>Close room</button>
      {/if}
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-3">
      <div class="card lg:col-span-2">
        <h2 class="hud font-display text-lg font-bold">Live ranking</h2>
        {#if ranking && ranking.entries.length}
          <table class="mt-3 w-full text-sm">
            <thead class="text-left muted">
              <tr><th class="py-1">#</th><th>User</th><th class="text-right">Score</th></tr>
            </thead>
            <tbody>
              {#each ranking.entries as e}
                <tr class="border-t">
                  <td class="py-1 font-mono">{e.rank}</td>
                  <td class="font-mono">{e.user_id.slice(0, 8)}…</td>
                  <td class="text-right">{(e.score_bp / 100).toFixed(1)}%</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <p class="mt-2 muted">No scores yet.</p>
        {/if}
      </div>

      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Participants</h2>
        <ul class="mt-2 space-y-1 text-sm">
          {#each participants as p}
            <li class="flex items-center justify-between">
              <span class="font-mono">{p.user_id.slice(0, 8)}…</span>
              <span
                class="badge"
                class:badge-mint={p.is_present}
                class:badge-neutral={!p.is_present}>{p.is_present ? "present" : "away"}</span
              >
            </li>
          {/each}
        </ul>
        {#if participants.length === 0}<p class="muted">Nobody yet.</p>{/if}
      </div>
    </div>

    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Event feed</h2>
      <ul class="mt-2 space-y-1 text-xs font-mono">
        {#each events as e}
          <li class="muted">[{new Date(e.at).toLocaleTimeString()}] {e.text}</li>
        {/each}
        {#if events.length === 0}<li class="muted">Waiting for activity…</li>{/if}
      </ul>
    </div>
  {/if}
</div>
