<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { page } from "$app/stores";
  import { api, wsUrl, ApiError } from "$lib/api/client";
  import type { Room, RoomMember, RankingResponse, RoomEvent } from "$lib/types";
  import Icon from "$lib/components/Icon.svelte";
  import { auth, hasRole } from "$lib/stores/auth";
  import { statusLabel } from "$lib/utils/format";

  let room: Room | null = null;
  let participants: RoomMember[] = [];
  let ranking: RankingResponse | null = null;
  let loading = true;
  let error = "";
  let connected = false;
  // Historical (persisted) room events, plus live WS frames merged on top.
  let history: RoomEvent[] = [];
  let liveEvents: { text: string; at: number }[] = [];
  let socket: WebSocket | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempts = 0;
  let destroyed = false;
  let busy = "";

  const roomId = $page.params.roomId;
  $: canManage = hasRole($auth.user, "teacher");
  $: myId = $auth.user?.id ?? "";

  /** Prefer a human name; fall back to a short id when the name is absent. */
  function who(name: string | null | undefined, id: string): string {
    return name && name.trim() ? name : `${id.slice(0, 8)}…`;
  }

  /** Map a WS frame type (dotted) or persisted event type to an Indonesian label. */
  const EVENT_LABEL: Record<string, string> = {
    // Live WS frames.
    "room.join": "bergabung",
    "room.leave": "keluar",
    "room.open": "membuka ruang",
    "room.close": "menutup ruang",
    "presence.join": "hadir",
    "presence.leave": "pergi",
    "quest.finalized": "quest difinalisasi",
    // Persisted room events (GET /rooms/{id}/events).
    joined: "bergabung",
    left: "keluar",
    opened: "membuka ruang",
    closed: "menutup ruang",
    invited: "diundang",
  };

  async function load() {
    try {
      room = await api.get<Room>(`/rooms/${roomId}`);
      participants = await api.get<RoomMember[]>(`/rooms/${roomId}/participants`);
      ranking = await api.get<RankingResponse>(`/rankings/rooms/${roomId}`);
      history = await api.get<RoomEvent[]>(`/rooms/${roomId}/events?limit=20`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ruang";
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
        if (msg.type === "resync") {
          // The bus dropped one or more frames for this socket (backpressure
          // — see docs/architecture.md); reload rather than trust a gap.
          load();
          return;
        }
        const actor = participants.find((p) => p.user_id === msg.user_id);
        const label = EVENT_LABEL[msg.type] ?? msg.type;
        liveEvents = [
          {
            text: `${actor ? who(actor.display_name, actor.user_id) : msg.user_id ? `${String(msg.user_id).slice(0, 8)}…` : "Ruang"} ${label}`,
            at: Date.now(),
          },
          ...liveEvents,
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
  async function lockRoom() {
    await act("lock", "lock");
  }
  async function unlockRoom() {
    await act("unlock", "unlock");
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

<svelte:head><title>{room?.name ?? "Ruang"} — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  {#if loading}
    <p class="muted">Memuat ruang…</p>
  {:else if error}
    <p class="alert-error">
      {error}
    </p>
  {:else if room}
    <a href="/rooms" class="text-sm text-primary">← Semua ruang</a>
    <div class="mt-2 flex flex-wrap items-center gap-3">
      <h1 class="font-display text-3xl font-bold">{room.name}</h1>
      <span
        class="badge"
        class:badge-mint={room.status === "open"}
        class:badge-neutral={room.status !== "open"}
      >
        {statusLabel(room.status)}
      </span>
      <span class="badge" class:badge-mint={connected} class:badge-neutral={!connected}>
        {connected ? "● live" : "○ offline"}
      </span>
    </div>
    <p class="mt-1 font-mono text-sm muted">Kode ruang: {room.code}</p>

    <div class="mt-4 flex flex-wrap gap-2">
      <button class="btn-ghost" on:click={join} disabled={busy === "join"}>Gabung</button>
      <button class="btn-ghost" on:click={leave} disabled={busy === "leave"}>Keluar</button>
      {#if canManage}
        <button class="btn-primary" on:click={openRoom} disabled={busy === "open"}>
          Buka ruang
        </button>
        <button class="btn-ghost" on:click={closeRoom} disabled={busy === "close"}>
          Tutup ruang
        </button>
        {#if room.status === "open"}
          {#if room.is_locked}
            <button class="btn-ghost" on:click={unlockRoom} disabled={busy === "unlock"}>
              <Icon name="lock-open" size="11px" /> Buka kunci
            </button>
          {:else}
            <button class="btn-ghost" on:click={lockRoom} disabled={busy === "lock"}>
              <Icon name="lock" size="11px" /> Kunci ruang
            </button>
          {/if}
        {/if}
      {/if}
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-3">
      <div class="card lg:col-span-2">
        <h2 class="hud font-display text-lg font-bold">Peringkat langsung</h2>
        {#if ranking && ranking.entries.length}
          <table class="mt-3 w-full text-sm">
            <thead class="text-left muted">
              <tr><th class="py-1">#</th><th>Pengguna</th><th class="text-right">Skor</th></tr>
            </thead>
            <tbody>
              {#each ranking.entries as e}
                <tr class="border-t">
                  <td class="py-1 font-mono">{e.rank}</td>
                  <td>{who(e.display_name, e.user_id)}</td>
                  <td class="text-right">{(e.score_bp / 100).toFixed(1)}%</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <p class="mt-2 muted">Belum ada skor.</p>
        {/if}
      </div>

      <div class="card">
        <h2 class="hud font-display text-lg font-bold">Peserta</h2>
        <ul class="mt-2 space-y-1 text-sm">
          {#each participants as p}
            <li class="flex items-center justify-between">
              <span>
                {who(p.display_name, p.user_id)}
                {#if p.user_id === myId}<span class="mono text-xs muted">(kamu)</span>{/if}
              </span>
              <span
                class="badge"
                class:badge-mint={p.is_present}
                class:badge-neutral={!p.is_present}>{p.is_present ? "hadir" : "tidak hadir"}</span
              >
            </li>
          {/each}
        </ul>
        {#if participants.length === 0}<p class="muted">Belum ada peserta.</p>{/if}
      </div>
    </div>

    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Umpan aktivitas</h2>
      <ul class="mt-2 space-y-1 text-xs font-mono">
        {#each liveEvents as e}
          <li class="text-ink2">[{new Date(e.at).toLocaleTimeString()}] {e.text}</li>
        {/each}
        {#each history as e}
          <li class="muted">
            [{new Date(e.created_at).toLocaleTimeString()}] {EVENT_LABEL[e.event_type] ??
              e.event_type}
          </li>
        {/each}
        {#if liveEvents.length === 0 && history.length === 0}
          <li class="muted">Menunggu aktivitas…</li>
        {/if}
      </ul>
    </div>
  {/if}
</div>
