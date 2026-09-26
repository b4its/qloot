<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { page } from "$app/stores";
  import { api, wsUrl, ApiError } from "$lib/api/client";
  import type { Room, RoomMember, RankingResponse, RoomEvent, LiveEntry } from "$lib/types";
  import Icon from "$lib/components/Icon.svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import { auth, hasRole } from "$lib/stores/auth";
  import { statusLabel } from "$lib/utils/format";

  let room: Room | null = null;
  let participants: RoomMember[] = [];
  let ranking: RankingResponse | null = null;
  let liveBoard: LiveEntry[] = [];
  let boardTab: "all" | "live" = "all";
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

  // Participant search and quick actions
  let participantSearch = "";
  let copiedFeedback = "";
  let copiedFeedbackTimeout: ReturnType<typeof setTimeout> | null = null;

  // Invite a specific email to this room and surface the invite code.
  let inviteEmail = "";
  let inviteNote = "";
  let inviteBusy = false;
  let inviteResult: { code: string; email: string | null } | null = null;
  let inviteError = "";

  const roomId = $page.params.roomId;
  $: canManage = hasRole($auth.user, "teacher");
  $: myId = $auth.user?.id ?? "";

  $: isMember = participants.some((p) => p.user_id === myId);
  $: presentParticipants = participants.filter((p) => p.is_present);

  $: filteredParticipants = participants.filter((p) => {
    if (!participantSearch.trim()) return true;
    const q = participantSearch.toLowerCase().trim();
    const nameMatch = (p.display_name ?? "").toLowerCase().includes(q);
    const idMatch = p.user_id.toLowerCase().includes(q);
    return nameMatch || idMatch;
  });

  /** Prefer a human name; fall back to a short id when the name is absent. */
  function who(name: string | null | undefined, id: string): string {
    return name && name.trim() ? name : `${id.slice(0, 8)}…`;
  }

  function setFeedback(msg: string) {
    copiedFeedback = msg;
    if (copiedFeedbackTimeout) clearTimeout(copiedFeedbackTimeout);
    copiedFeedbackTimeout = setTimeout(() => {
      copiedFeedback = "";
    }, 2500);
  }

  async function copyCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      setFeedback(`Kode ruang "${code}" berhasil disalin!`);
    } catch {
      setFeedback(`Kode ruang "${code}" disalin!`);
    }
  }

  async function copyRoomLink() {
    try {
      const url = window.location.href;
      await navigator.clipboard.writeText(url);
      setFeedback("Tautan ruang berhasil disalin ke clipboard!");
    } catch {
      setFeedback("Tautan ruang disalin!");
    }
  }

  /** Map a WS frame type (dotted) or persisted event type to an Indonesian label. */
  const EVENT_LABEL: Record<string, string> = {
    // Live WS frames.
    "room.join": "bergabung ke ruang",
    "room.leave": "keluar dari ruang",
    "room.open": "membuka ruang",
    "room.close": "menutup ruang",
    "presence.join": "hadir dalam sesi",
    "presence.leave": "meninggalkan sesi",
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
      const [r, p, rk, h, lb] = await Promise.all([
        api.get<Room>(`/rooms/${roomId}`),
        api.get<RoomMember[]>(`/rooms/${roomId}/participants`),
        api.get<RankingResponse>(`/rankings/rooms/${roomId}`),
        api.get<RoomEvent[]>(`/rooms/${roomId}/events?limit=20`),
        api.get<LiveEntry[]>(`/rooms/${roomId}/live`),
      ]);
      room = r;
      participants = p;
      ranking = rk;
      history = h;
      liveBoard = lb;
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

  /** Invite someone to this room (owner/teacher); returns a redeemable code. */
  async function sendInvite() {
    inviteError = "";
    inviteResult = null;
    inviteBusy = true;
    try {
      const inv = await api.post<{ code: string; email: string | null }>(
        `/rooms/${roomId}/invite`,
        { email: inviteEmail.trim() || null, note: inviteNote.trim() || null },
      );
      inviteResult = { code: inv.code, email: inv.email };
      inviteEmail = "";
      inviteNote = "";
    } catch (e) {
      inviteError = e instanceof ApiError ? e.message : "Gagal mengundang";
    } finally {
      inviteBusy = false;
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
    if (copiedFeedbackTimeout) clearTimeout(copiedFeedbackTimeout);
    socket?.close();
  });
</script>

<svelte:head><title>{room?.name ?? "Ruang"} — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  {#if loading}
    <div class="space-y-4">
      <Skeleton rows={2} />
      <Skeleton rows={6} />
    </div>
  {:else if error}
    <div class="space-y-4">
      <a
        href="/rooms"
        class="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
      >
        <Icon name="arrow-left" size="10px" />
        <span>Kembali ke Semua Ruang</span>
      </a>
      <p class="alert-error">
        {error}
      </p>
    </div>
  {:else if room}
    <!-- Breadcrumbs & Quick link -->
    <div class="flex items-center justify-between">
      <a
        href="/rooms"
        class="inline-flex items-center gap-1.5 text-xs text-primary hover:underline font-medium"
      >
        <Icon name="arrow-left" size="10px" />
        <span>Semua Ruang</span>
      </a>
      <button
        type="button"
        class="btn-ghost !py-1 !px-2 text-xs flex items-center gap-1.5 text-muted hover:text-foreground"
        on:click={copyRoomLink}
      >
        <Icon name="share-nodes" size="11px" />
        <span>Bagikan Tautan</span>
      </button>
    </div>

    <!-- Toast Feedback Banner -->
    {#if copiedFeedback}
      <div
        class="mt-3 rounded-sm border border-mint/40 bg-mint/10 px-3 py-2 text-xs text-mint flex items-center gap-2"
      >
        <Icon name="check" size="12px" />
        <span>{copiedFeedback}</span>
      </div>
    {/if}

    <!-- Room Title & Status Header -->
    <div class="mt-3 flex flex-wrap items-start justify-between gap-4 border-b pb-4">
      <div>
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="font-display text-3xl font-bold">{room.name}</h1>
          <span
            class="badge text-xs"
            class:badge-mint={room.status === "open"}
            class:badge-neutral={room.status !== "open"}
          >
            {statusLabel(room.status)}
          </span>
          {#if room.is_locked}
            <span
              class="badge border border-amber-500/40 text-amber-400 text-xs flex items-center gap-1"
            >
              <Icon name="lock" size="9px" />
              <span>Terkunci</span>
            </span>
          {/if}
          <span
            class="badge text-xs flex items-center gap-1.5"
            class:badge-mint={connected}
            class:badge-neutral={!connected}
          >
            <span
              class="w-1.5 h-1.5 rounded-full"
              class:bg-mint={connected}
              class:bg-muted={!connected}
            ></span>
            <span>{connected ? "Live Realtime" : "Terputus"}</span>
          </span>
        </div>

        <div class="mt-2 flex flex-wrap items-center gap-3 text-xs">
          <div class="flex items-center gap-1.5 surface border px-2 py-1 rounded-xs">
            <span class="muted">Kode Ruang:</span>
            <span class="font-mono font-bold text-primary tracking-wider">{room.code}</span>
            <button
              type="button"
              class="ml-1 text-muted hover:text-foreground p-0.5"
              title="Salin Kode"
              on:click={() => copyCode(room?.code ?? "")}
            >
              <Icon name="copy" size="11px" />
            </button>
          </div>
          <span class="muted">
            Kapasitas: <strong class="text-foreground">{room.max_participants}</strong> peserta maks.
          </span>
          <span class="muted">
            Tipe: <strong class="text-foreground">{room.is_public ? "Publik" : "Privat"}</strong>
          </span>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex flex-wrap items-center gap-2">
        {#if !isMember}
          <button class="btn-primary !py-1.5 text-xs" on:click={join} disabled={busy === "join"}>
            <Icon name="arrow-right-to-bracket" size="12px" />
            <span>{busy === "join" ? "Memproses…" : "Gabung Ruang"}</span>
          </button>
        {:else}
          <button
            class="btn-secondary !py-1.5 text-xs"
            on:click={leave}
            disabled={busy === "leave"}
          >
            <Icon name="arrow-right-from-bracket" size="12px" />
            <span>{busy === "leave" ? "Memproses…" : "Keluar Ruang"}</span>
          </button>
        {/if}

        {#if canManage}
          {#if room.status !== "open"}
            <button
              class="btn-primary !py-1.5 text-xs"
              on:click={openRoom}
              disabled={busy === "open"}
            >
              <Icon name="door-open" size="12px" />
              <span>{busy === "open" ? "Membuka…" : "Buka Ruang"}</span>
            </button>
          {:else}
            <button
              class="btn-ghost !py-1.5 text-xs"
              on:click={closeRoom}
              disabled={busy === "close"}
            >
              <Icon name="door-closed" size="12px" />
              <span>{busy === "close" ? "Menutup…" : "Tutup Ruang"}</span>
            </button>
          {/if}

          {#if room.status === "open"}
            {#if room.is_locked}
              <button
                class="btn-ghost !py-1.5 text-xs"
                on:click={unlockRoom}
                disabled={busy === "unlock"}
              >
                <Icon name="lock-open" size="11px" />
                <span>{busy === "unlock" ? "Membuka…" : "Buka Kunci"}</span>
              </button>
            {:else}
              <button
                class="btn-ghost !py-1.5 text-xs text-amber-400"
                on:click={lockRoom}
                disabled={busy === "lock"}
              >
                <Icon name="lock" size="11px" />
                <span>{busy === "lock" ? "Mengunci…" : "Kunci Ruang"}</span>
              </button>
            {/if}
          {/if}
        {/if}
      </div>
    </div>

    <!-- Teacher Invite Panel -->
    {#if canManage}
      <div class="card mt-6 border-secondary/30">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Icon name="user-plus" size="14px" class="text-secondary" />
            <h2 class="hud font-display text-base font-bold">Undang peserta</h2>
          </div>
          <span class="text-xs muted font-mono">Panel Pengelola</span>
        </div>
        <p class="mt-1 text-xs muted">
          Undang lewat email peserta secara langsung atau buat kode undangan khusus untuk dibagikan.
        </p>
        <div class="mt-3 grid gap-2 sm:grid-cols-2">
          <label class="flex flex-col text-xs">
            <span class="muted mb-1 font-medium">Email Peserta (Opsional)</span>
            <input
              class="input text-xs"
              type="email"
              bind:value={inviteEmail}
              placeholder="nama.siswa@contoh.com"
            />
          </label>
          <label class="flex flex-col text-xs">
            <span class="muted mb-1 font-medium">Catatan Undangan (Opsional)</span>
            <input
              class="input text-xs"
              bind:value={inviteNote}
              placeholder="mis. Kelompok Sains Kelas XII"
            />
          </label>
        </div>
        <div class="mt-3 flex items-center gap-2">
          <button class="btn-primary !py-1.5 text-xs" on:click={sendInvite} disabled={inviteBusy}>
            <Icon name="paper-plane" size="11px" />
            <span>{inviteBusy ? "Mengundang…" : "Buat Undangan"}</span>
          </button>
        </div>
        {#if inviteError}<p class="alert-error mt-2">{inviteError}</p>{/if}
        {#if inviteResult}
          <div
            class="mt-3 rounded-sm border border-secondary/40 surface p-3 flex flex-wrap items-center justify-between gap-2"
          >
            <div>
              <p class="mono-label text-[10px] text-secondary">Kode Undangan Baru</p>
              <p class="mt-0.5 font-mono text-lg font-bold text-foreground tracking-wider">
                {inviteResult.code}
              </p>
              {#if inviteResult.email}
                <p class="mt-0.5 text-xs muted">
                  Ditujukan untuk: <strong class="text-foreground">{inviteResult.email}</strong>
                </p>
              {/if}
            </div>
            <button
              type="button"
              class="btn-secondary !py-1 text-xs flex items-center gap-1.5"
              on:click={() => copyCode(inviteResult?.code ?? "")}
            >
              <Icon name="copy" size="11px" />
              <span>Salin Kode</span>
            </button>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Main Grid: Leaderboard & Participants -->
    <div class="mt-6 grid gap-6 lg:grid-cols-3">
      <!-- Leaderboard Column (2 cols) -->
      <div class="card lg:col-span-2">
        <div class="flex flex-wrap items-center justify-between gap-2 border-b pb-3">
          <div>
            <h2 class="hud font-display text-lg font-bold">Papan Peringkat</h2>
            <p class="text-xs muted">Hasil kompetisi dan capaian nilai peserta di dalam ruang.</p>
          </div>
          <div class="flex items-center gap-1 rounded-sm border p-0.5 surface text-xs">
            <button
              type="button"
              class="px-2.5 py-1 rounded-xs font-medium transition-colors"
              class:bg-primary={boardTab === "live"}
              class:text-[#05060A]={boardTab === "live"}
              class:muted={boardTab !== "live"}
              on:click={() => (boardTab = "live")}
            >
              Langsung ({liveBoard.length})
            </button>
            <button
              type="button"
              class="px-2.5 py-1 rounded-xs font-medium transition-colors"
              class:bg-primary={boardTab === "all"}
              class:text-[#05060A]={boardTab === "all"}
              class:muted={boardTab !== "all"}
              on:click={() => (boardTab = "all")}
            >
              Akumulasi
            </button>
          </div>
        </div>

        {#if boardTab === "live"}
          {#if liveBoard.length > 0}
            <div class="overflow-x-auto mt-2">
              <table class="w-full text-xs">
                <thead>
                  <tr class="border-b text-left muted text-[11px]">
                    <th class="py-2 px-3 w-12">#</th>
                    <th class="py-2 px-3">Peserta</th>
                    <th class="py-2 px-3 text-center">Kehadiran</th>
                    <th class="py-2 px-3 text-right">Skor</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-surface-border">
                  {#each liveBoard as e}
                    <tr class="hover:bg-surface/50 transition-colors">
                      <td class="py-2.5 px-3 font-mono font-bold">
                        {#if e.rank === 1}
                          <span class="text-amber-400">🥇 1</span>
                        {:else if e.rank === 2}
                          <span class="text-slate-300">🥈 2</span>
                        {:else if e.rank === 3}
                          <span class="text-amber-600">🥉 3</span>
                        {:else}
                          {e.rank}
                        {/if}
                      </td>
                      <td class="py-2.5 px-3">
                        <span class="font-medium text-foreground"
                          >{who(e.display_name, e.user_id)}</span
                        >
                        {#if e.user_id === myId}
                          <span class="badge badge-indigo text-[9px] ml-1">Kamu</span>
                        {/if}
                      </td>
                      <td class="py-2.5 px-3 text-center">
                        <span
                          class="badge text-[10px]"
                          class:badge-mint={e.is_present}
                          class:badge-neutral={!e.is_present}
                        >
                          {e.is_present ? "Hadir" : "Offline"}
                        </span>
                      </td>
                      <td class="py-2.5 px-3 text-right font-mono font-bold text-primary">
                        {(e.score_bp / 100).toFixed(1)}%
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <div class="py-12 text-center text-xs muted space-y-1">
              <Icon name="chart-simple" size="24px" class="mx-auto text-muted mb-2" />
              <p>Belum ada skor langsung dalam sesi ini.</p>
              <p class="text-[11px]">
                Nilai akan muncul otomatis saat peserta menyelesaikan kuis atau quest.
              </p>
            </div>
          {/if}
        {:else if ranking && ranking.entries.length}
          <div class="overflow-x-auto mt-2">
            <table class="w-full text-xs">
              <thead>
                <tr class="border-b text-left muted text-[11px]">
                  <th class="py-2 px-3 w-12">#</th>
                  <th class="py-2 px-3">Peserta</th>
                  <th class="py-2 px-3 text-right">Skor Total</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-surface-border">
                {#each ranking.entries as e}
                  <tr class="hover:bg-surface/50 transition-colors">
                    <td class="py-2.5 px-3 font-mono font-bold">
                      {#if e.rank === 1}
                        <span class="text-amber-400">🥇 1</span>
                      {:else if e.rank === 2}
                        <span class="text-slate-300">🥈 2</span>
                      {:else if e.rank === 3}
                        <span class="text-amber-600">🥉 3</span>
                      {:else}
                        {e.rank}
                      {/if}
                    </td>
                    <td class="py-2.5 px-3">
                      <span class="font-medium text-foreground"
                        >{who(e.display_name, e.user_id)}</span
                      >
                      {#if e.user_id === myId}
                        <span class="badge badge-indigo text-[9px] ml-1">Kamu</span>
                      {/if}
                    </td>
                    <td class="py-2.5 px-3 text-right font-mono font-bold text-primary">
                      {(e.score_bp / 100).toFixed(1)}%
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <div class="py-12 text-center text-xs muted space-y-1">
            <Icon name="trophy" size="24px" class="mx-auto text-muted mb-2" />
            <p>Belum ada skor akumulasi dalam ruang ini.</p>
          </div>
        {/if}
      </div>

      <!-- Participants Column (1 col) -->
      <div class="card space-y-3">
        <div class="flex items-center justify-between border-b pb-2">
          <div>
            <h2 class="hud font-display text-base font-bold">Peserta Ruang</h2>
            <p class="text-[11px] muted">
              {presentParticipants.length} aktif dari {participants.length} terdaftar
            </p>
          </div>
          <span class="badge badge-neutral text-xs font-mono">{participants.length}</span>
        </div>

        {#if participants.length > 5}
          <div class="relative">
            <input
              type="text"
              class="input text-xs !py-1 w-full"
              placeholder="Cari peserta..."
              bind:value={participantSearch}
            />
          </div>
        {/if}

        <div class="max-h-80 overflow-y-auto pr-1 space-y-1.5">
          {#each filteredParticipants as p}
            <div
              class="flex items-center justify-between p-2 rounded-sm border surface hover:border-primary/40 transition-colors text-xs"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span
                  class="w-2 h-2 rounded-full shrink-0"
                  class:bg-mint={p.is_present}
                  class:bg-muted={!p.is_present}
                  title={p.is_present ? "Sedang aktif" : "Offline"}
                ></span>
                <div class="truncate">
                  <span class="font-medium text-foreground block truncate">
                    {who(p.display_name, p.user_id)}
                  </span>
                  {#if p.user_id === myId}
                    <span class="text-[10px] text-primary">(Kamu)</span>
                  {/if}
                </div>
              </div>
              <div class="flex items-center gap-1 shrink-0">
                {#if p.role === "teacher"}
                  <span class="badge badge-amber text-[9px]">Guru</span>
                {/if}
                <span
                  class="badge text-[9px]"
                  class:badge-mint={p.is_present}
                  class:badge-neutral={!p.is_present}
                >
                  {p.is_present ? "Hadir" : "Offline"}
                </span>
              </div>
            </div>
          {/each}

          {#if participants.length === 0}
            <p class="text-xs muted py-4 text-center">Belum ada peserta yang bergabung.</p>
          {:else if filteredParticipants.length === 0}
            <p class="text-xs muted py-4 text-center">Tidak ada peserta yang cocok.</p>
          {/if}
        </div>
      </div>
    </div>

    <!-- Live Activity Feed -->
    <div class="card mt-6">
      <div class="flex items-center justify-between border-b pb-2">
        <div class="flex items-center gap-2">
          <Icon name="clock-rotate-left" size="13px" class="text-primary" />
          <h2 class="hud font-display text-base font-bold">Umpan Aktivitas Sesi</h2>
        </div>
        <span class="badge text-[10px] font-mono muted">
          {liveEvents.length + history.length} peristiwa
        </span>
      </div>

      <div class="mt-3 max-h-60 overflow-y-auto space-y-1 font-mono text-xs">
        {#each liveEvents as e}
          <div
            class="flex items-center gap-2 py-1 px-2 rounded-xs bg-primary/5 text-primary border-l-2 border-primary"
          >
            <span class="text-[10px] muted">[{new Date(e.at).toLocaleTimeString()}]</span>
            <span class="text-foreground">{e.text}</span>
            <span class="badge badge-mint text-[8px] ml-auto">LIVE</span>
          </div>
        {/each}
        {#each history as e}
          <div class="flex items-center gap-2 py-1 px-2 text-muted">
            <span class="text-[10px] muted">[{new Date(e.created_at).toLocaleTimeString()}]</span>
            <span>
              {EVENT_LABEL[e.event_type] ?? e.event_type}
            </span>
          </div>
        {/each}
        {#if liveEvents.length === 0 && history.length === 0}
          <div class="text-center py-6 text-xs muted">Menunggu aktivitas peserta dalam ruang…</div>
        {/if}
      </div>
    </div>
  {/if}
</div>
