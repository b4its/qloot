<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Room } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { statusLabel, paginate } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";

  const PAGE_SIZE = 12;
  let rooms: Room[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let joinCode = "";
  let joinError = "";
  let joinLoading = false;
  let showCreate = false;
  let createBusy = false;
  let currentPage = 1;
  let newRoom = { name: "", max_participants: 100, is_public: true };
  // Inline editing of an existing room (PATCH /rooms/{id}): teachers only.
  let editingRoom: string | null = null;
  let editRoomDraft = { name: "", max_participants: 100, is_public: true };
  let editBusy = false;

  function startEditRoom(r: Room) {
    error = "";
    message = "";
    editingRoom = r.id;
    editRoomDraft = {
      name: r.name,
      max_participants: r.max_participants ?? 100,
      is_public: r.is_public ?? true,
    };
  }

  async function saveRoom(id: string) {
    error = "";
    message = "";
    if (editRoomDraft.name.trim().length < 2) {
      error = "Nama ruang minimal 2 karakter.";
      return;
    }
    if (!(editRoomDraft.max_participants >= 2 && editRoomDraft.max_participants <= 1000)) {
      error = "Kapasitas harus antara 2 dan 1000 peserta.";
      return;
    }
    editBusy = true;
    try {
      const updated = await api.patch<Room>(`/rooms/${id}`, {
        name: editRoomDraft.name.trim(),
        max_participants: editRoomDraft.max_participants,
        is_public: editRoomDraft.is_public,
      });
      rooms = rooms.map((r) => (r.id === id ? { ...r, ...updated } : r));
      editingRoom = null;
      message = "Ruang diperbarui.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui ruang";
    } finally {
      editBusy = false;
    }
  }

  // Search & Filter state
  let searchQuery = "";
  let statusFilter: "all" | "open" | "closed" | "locked" = "all";
  let typeFilter: "all" | "public" | "private" = "all";
  let copiedCode = "";
  let copyTimeout: ReturnType<typeof setTimeout> | null = null;

  $: canManage = hasRole($auth.user, "teacher");

  $: filteredRooms = rooms.filter((r) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchName = r.name.toLowerCase().includes(q);
      const matchCode = r.code.toLowerCase().includes(q);
      if (!matchName && !matchCode) return false;
    }
    if (statusFilter === "open" && r.status !== "open") return false;
    if (statusFilter === "closed" && r.status !== "closed") return false;
    if (statusFilter === "locked" && !r.is_locked) return false;

    if (typeFilter === "public" && !r.is_public) return false;
    if (typeFilter === "private" && r.is_public) return false;

    return true;
  });

  $: totalPages = Math.max(1, Math.ceil(filteredRooms.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedRooms = paginate(filteredRooms, currentPage, PAGE_SIZE);

  // Statistics counters
  $: openRoomsCount = rooms.filter((r) => r.status === "open").length;
  $: lockedRoomsCount = rooms.filter((r) => r.is_locked).length;
  $: publicRoomsCount = rooms.filter((r) => r.is_public).length;

  async function load() {
    loading = true;
    error = "";
    message = "";
    try {
      rooms = await api.get<Room[]>("/rooms?limit=200");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ruang";
    } finally {
      loading = false;
    }
  }

  async function copyRoomCode(code: string, event?: Event) {
    if (event) event.preventDefault();
    try {
      await navigator.clipboard.writeText(code);
      copiedCode = code;
      if (copyTimeout) clearTimeout(copyTimeout);
      copyTimeout = setTimeout(() => {
        copiedCode = "";
      }, 2000);
    } catch {
      copiedCode = code;
      setTimeout(() => (copiedCode = ""), 2000);
    }
  }

  async function pasteJoinCode() {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        joinCode = text.trim().slice(0, 12).toUpperCase();
      }
    } catch {
      // clipboard access denied or unsupported
    }
  }

  function resetFilters() {
    searchQuery = "";
    statusFilter = "all";
    typeFilter = "all";
    currentPage = 1;
  }

  async function joinByCode() {
    joinError = "";
    joinLoading = true;
    try {
      const room = await api.post<Room>("/rooms/join-by-code", {
        code: joinCode.trim().toUpperCase(),
      });
      await goto(`/rooms/${room.id}`);
    } catch (e) {
      joinError = e instanceof ApiError ? e.message : "Gagal bergabung ke ruang";
    } finally {
      joinLoading = false;
    }
  }

  /** Redeem an invitation code (POST /rooms/invitations/accept). */
  async function acceptInvitation() {
    joinError = "";
    joinLoading = true;
    try {
      const member = await api.post<{ room_id: string }>("/rooms/invitations/accept", {
        code: joinCode.trim().toUpperCase(),
      });
      await goto(`/rooms/${member.room_id}`);
    } catch (e) {
      joinError = e instanceof ApiError ? e.message : "Gagal menerima undangan";
    } finally {
      joinLoading = false;
    }
  }

  async function createRoom() {
    error = "";
    message = "";
    if (newRoom.name.trim().length < 2) {
      error = "Nama ruang minimal 2 karakter.";
      return;
    }
    if (!(newRoom.max_participants >= 2 && newRoom.max_participants <= 1000)) {
      error = "Kapasitas harus antara 2 dan 1000 peserta.";
      return;
    }
    createBusy = true;
    try {
      const room = await api.post<Room>("/rooms", newRoom);
      showCreate = false;
      await goto(`/rooms/${room.id}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat ruang";
    } finally {
      createBusy = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Ruang Kompetisi | QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <p class="mono-label">Kompetisi Langsung & Belajar Bersama</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Ruang Belajar</h1>
      <p class="mt-1 text-sm muted">
        Bergabung dalam ruang belajar interaktif, ujian real-time, dan leaderboard langsung.
      </p>
    </div>
    {#if canManage}
      <button class="btn-primary" on:click={() => (showCreate = !showCreate)}>
        <Icon name="plus" size="12px" />
        <span>{showCreate ? "Tutup Form" : "Buat Ruang"}</span>
      </button>
    {/if}
  </div>

  <!-- Overview Metrics -->
  {#if !loading && rooms.length > 0}
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-3">
        <span class="mono-label text-[10px]">Total Ruang</span>
        <div class="mt-1 font-display text-xl font-bold">{rooms.length}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">Ruang Terbuka</span>
        <div class="mt-1 font-display text-xl font-bold text-mint">{openRoomsCount}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">Ruang Terkunci</span>
        <div class="mt-1 font-display text-xl font-bold text-amber-500">{lockedRoomsCount}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">Ruang Publik</span>
        <div class="mt-1 font-display text-xl font-bold text-primary">{publicRoomsCount}</div>
      </div>
    </div>
  {/if}

  <!-- Join with Code Card -->
  <div class="card mt-6">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h2 class="hud font-display text-lg font-bold">Gabung dengan Kode</h2>
        <p class="text-xs muted mt-0.5">
          Punya kode akses dari guru atau teman? Masukkan kode 6 karakter di bawah ini.
        </p>
      </div>
    </div>
    <div class="mt-3 flex flex-wrap items-center gap-2">
      <div class="relative w-full max-w-xs">
        <input
          class="input w-full uppercase font-mono tracking-wider text-base !py-1.5"
          placeholder="MISAL: ABC123"
          bind:value={joinCode}
          maxlength="12"
          aria-label="Kode ruang"
          on:keydown={(e) => e.key === "Enter" && joinCode.length >= 4 && joinByCode()}
        />
        {#if joinCode}
          <button
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
            on:click={() => (joinCode = "")}
            aria-label="Bersihkan kode"
          >
            ✕
          </button>
        {/if}
      </div>
      <button
        type="button"
        class="btn-ghost !py-1.5 text-xs"
        on:click={pasteJoinCode}
        title="Tempel dari Clipboard"
      >
        <Icon name="paste" size="12px" />
        <span>Tempel</span>
      </button>
      <button
        class="btn-primary !py-1.5 text-xs"
        on:click={joinByCode}
        disabled={joinLoading || joinCode.length < 4}
      >
        {joinLoading ? "Bergabung…" : "Gabung Ruang"}
      </button>
      <button
        class="btn-secondary !py-1.5 text-xs"
        on:click={acceptInvitation}
        disabled={joinLoading || joinCode.length < 4}
      >
        Terima undangan
      </button>
    </div>
    {#if joinError}<p class="alert-error mt-2" role="alert" aria-live="assertive">
        {joinError}
      </p>{/if}
  </div>

  <!-- Create Room Form (Teacher only) -->
  {#if showCreate}
    <div class="card mt-4 border-primary/40 shadow-lg">
      <div class="flex items-center justify-between border-b pb-2">
        <h2 class="hud font-display text-lg font-bold">Buat Ruang Baru</h2>
        <button class="btn-icon" on:click={() => (showCreate = false)} aria-label="Tutup">
          <Icon name="xmark" size="12px" />
        </button>
      </div>
      <div class="mt-3 grid gap-3 sm:grid-cols-3">
        <div class="sm:col-span-2">
          <label class="block text-xs font-medium muted mb-1" for="room-name">Nama Ruang</label>
          <input
            id="room-name"
            class="input w-full"
            placeholder="mis. Ruang Belajar Fisika Inti"
            bind:value={newRoom.name}
          />
        </div>
        <div>
          <label class="block text-xs font-medium muted mb-1" for="max-parts"
            >Kapasitas Maksimal</label
          >
          <input
            id="max-parts"
            class="input w-full font-mono"
            type="number"
            min="2"
            max="1000"
            bind:value={newRoom.max_participants}
          />
        </div>
      </div>
      <label class="mt-3 flex items-center gap-2 text-sm cursor-pointer select-none">
        <input type="checkbox" bind:checked={newRoom.is_public} class="rounded text-primary" />
        <span class="font-medium">Jadikan ruang publik</span>
        <span class="text-xs muted">(dapat ditemukan di daftar ruang oleh semua siswa)</span>
      </label>
      <div class="mt-4 flex items-center gap-2">
        <button
          class="btn-primary"
          on:click={createRoom}
          disabled={createBusy || newRoom.name.length < 2}
        >
          {createBusy ? "Membuat…" : "Simpan & Masuk Ruang"}
        </button>
        <button class="btn-ghost" on:click={() => (showCreate = false)}>Batal</button>
      </div>
    </div>
  {/if}

  {#if message}
    <p class="alert-ok mt-4" role="status" aria-live="polite">{message}</p>
  {/if}
  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">
      {error}
    </p>
  {/if}

  <!-- Search & Filter Controls -->
  <div class="mt-6 flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2 flex-1">
      <div class="relative w-full sm:w-64">
        <input
          type="text"
          class="input text-xs !py-1.5 w-full"
          placeholder="Cari nama atau kode ruang..."
          bind:value={searchQuery}
          aria-label="Cari ruang"
        />
        {#if searchQuery}
          <button
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
            on:click={() => (searchQuery = "")}
            aria-label="Bersihkan pencarian"
          >
            ✕
          </button>
        {/if}
      </div>

      <!-- Status filters -->
      <div class="flex items-center gap-1 rounded-sm border p-1 surface text-xs">
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={statusFilter === "all"}
          class:text-[#05060A]={statusFilter === "all"}
          class:muted={statusFilter !== "all"}
          on:click={() => (statusFilter = "all")}
        >
          Semua ({rooms.length})
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={statusFilter === "open"}
          class:text-[#05060A]={statusFilter === "open"}
          class:muted={statusFilter !== "open"}
          on:click={() => (statusFilter = "open")}
        >
          Buka
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={statusFilter === "locked"}
          class:text-[#05060A]={statusFilter === "locked"}
          class:muted={statusFilter !== "locked"}
          on:click={() => (statusFilter = "locked")}
        >
          Terkunci
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={statusFilter === "closed"}
          class:text-[#05060A]={statusFilter === "closed"}
          class:muted={statusFilter !== "closed"}
          on:click={() => (statusFilter = "closed")}
        >
          Ditutup
        </button>
      </div>

      <!-- Type filters -->
      <div class="flex items-center gap-1 rounded-sm border p-1 surface text-xs">
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={typeFilter === "all"}
          class:text-[#05060A]={typeFilter === "all"}
          class:muted={typeFilter !== "all"}
          on:click={() => (typeFilter = "all")}
        >
          Semua Tipe
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={typeFilter === "public"}
          class:text-[#05060A]={typeFilter === "public"}
          class:muted={typeFilter !== "public"}
          on:click={() => (typeFilter = "public")}
        >
          Publik
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-xs font-medium transition-colors"
          class:bg-primary={typeFilter === "private"}
          class:text-[#05060A]={typeFilter === "private"}
          class:muted={typeFilter !== "private"}
          on:click={() => (typeFilter = "private")}
        >
          Privat
        </button>
      </div>
    </div>
  </div>

  <!-- Room Grid Content -->
  {#if loading}
    <div class="mt-6"><Skeleton rows={4} /></div>
  {:else if rooms.length === 0}
    <EmptyState
      icon="door-closed"
      title="Belum ada ruang yang tersedia"
      description="Buat ruang baru jika Anda seorang guru, atau gunakan kode gabung."
    />
  {:else if filteredRooms.length === 0}
    <EmptyState
      icon="magnifying-glass"
      title="Tidak ada ruang yang cocok"
      description="Tidak ada ruang yang sesuai dengan filter atau pencarian Anda."
      actionLabel="Reset Filter"
      onAction={resetFilters}
    />
  {:else}
    <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each pagedRooms as room}
        <div
          class="card lift flex flex-col justify-between hover:border-primary/60 transition-all p-4"
        >
          <div>
            {#if editingRoom === room.id}
              <!-- Inline edit form -->
              <input
                class="input !py-1.5"
                placeholder="Nama ruang"
                bind:value={editRoomDraft.name}
              />
              <div class="mt-2 grid grid-cols-2 gap-2">
                <label class="block">
                  <span class="mono-label text-[10px]">Kapasitas</span>
                  <input
                    class="input !py-1 text-sm"
                    type="number"
                    min="2"
                    max="1000"
                    bind:value={editRoomDraft.max_participants}
                  />
                </label>
                <label class="flex items-end gap-2 text-xs pb-1.5">
                  <input type="checkbox" bind:checked={editRoomDraft.is_public} />
                  <span>Publik</span>
                </label>
              </div>
              <div class="mt-2 flex gap-2">
                <button
                  class="btn-primary !py-1 text-xs"
                  on:click={() => saveRoom(room.id)}
                  disabled={editBusy}
                >
                  {editBusy ? "Menyimpan…" : "Simpan"}
                </button>
                <button class="btn-ghost !py-1 text-xs" on:click={() => (editingRoom = null)}>
                  Batal
                </button>
              </div>
            {:else}
              <div class="flex items-start justify-between gap-2">
                <h2 class="font-display text-lg font-bold leading-snug line-clamp-2">
                  <a href={`/rooms/${room.id}`} class="hover:text-primary transition-colors">
                    {room.name}
                  </a>
                </h2>
                <div class="flex flex-col items-end gap-1 shrink-0">
                  <span
                    class="badge text-[10px]"
                    class:badge-mint={room.status === "open"}
                    class:badge-amber={room.status !== "open" && room.is_locked}
                    class:badge-neutral={room.status === "closed"}
                  >
                    {statusLabel(room.status)}
                  </span>
                  {#if room.is_locked}
                    <span
                      class="badge border border-amber-500/40 text-amber-400 text-[9px] flex items-center gap-1"
                    >
                      <Icon name="lock" size="8px" />
                      <span>Terkunci</span>
                    </span>
                  {/if}
                </div>
              </div>

              <div class="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                <span class="badge text-[10px] border border-surface-border">
                  {#if room.is_public}
                    <span class="text-mint flex items-center gap-1"
                      ><Icon name="globe" size="9px" /> Publik</span
                    >
                  {:else}
                    <span class="text-muted flex items-center gap-1"
                      ><Icon name="lock" size="9px" /> Privat</span
                    >
                  {/if}
                </span>
                <span class="text-[11px] muted">
                  Maks. {room.max_participants} peserta
                </span>
              </div>
            {/if}
          </div>

          <div class="mt-4 pt-3 border-t flex items-center justify-between text-xs">
            <div class="flex items-center gap-1.5 font-mono">
              <span class="text-[11px] muted">Kode:</span>
              <span class="font-bold text-primary tracking-wider">{room.code}</span>
              <button
                type="button"
                class="text-muted hover:text-foreground p-1 transition-colors"
                title="Salin kode"
                aria-label={`Salin kode ruang ${room.code}`}
                on:click={(e) => copyRoomCode(room.code, e)}
              >
                {#if copiedCode === room.code}
                  <span class="text-[10px] text-mint font-sans font-bold">Tersalin!</span>
                {:else}
                  <Icon name="copy" size="11px" />
                {/if}
              </button>
            </div>
            <div class="flex items-center gap-1">
              {#if canManage && editingRoom !== room.id}
                <button
                  type="button"
                  class="btn-ghost !py-1 !px-2 text-xs"
                  on:click={() => startEditRoom(room)}
                  aria-label={`Ubah ruang ${room.name}`}
                >
                  <Icon name="pen" size="10px" />
                </button>
              {/if}
              <a
                href={`/rooms/${room.id}`}
                class="btn-ghost !py-1 !px-2.5 text-xs text-primary font-medium flex items-center gap-1"
              >
                <span>Masuk</span>
                <Icon name="arrow-right" size="10px" />
              </a>
            </div>
          </div>
        </div>
      {/each}
    </div>

    <Pagination
      page={currentPage}
      pageSize={PAGE_SIZE}
      total={filteredRooms.length}
      {loading}
      label="ruang"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>
