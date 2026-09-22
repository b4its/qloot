<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Room } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { statusLabel } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import { paginate } from "$lib/utils/format";

  const PAGE_SIZE = 12;
  let rooms: Room[] = [];
  let loading = true;
  let error = "";
  let joinCode = "";
  let joinError = "";
  let joinLoading = false;
  let showCreate = false;
  let createBusy = false;
  let currentPage = 1;
  let newRoom = { name: "", max_participants: 100, is_public: true };

  $: canManage = hasRole($auth.user, "teacher");
  $: totalPages = Math.max(1, Math.ceil(rooms.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedRooms = paginate(rooms, currentPage, PAGE_SIZE);

  async function load() {
    loading = true;
    error = "";
    try {
      rooms = await api.get<Room[]>("/rooms?limit=200");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ruang";
    } finally {
      loading = false;
    }
  }

  async function joinByCode() {
    joinError = "";
    joinLoading = true;
    try {
      const room = await api.post<Room>("/rooms/join-by-code", {
        code: joinCode.trim().toUpperCase(),
      });
      window.location.href = `/rooms/${room.id}`;
    } catch (e) {
      joinError = e instanceof ApiError ? e.message : "Gagal bergabung ke ruang";
    } finally {
      joinLoading = false;
    }
  }

  async function createRoom() {
    error = "";
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
      window.location.href = `/rooms/${room.id}`;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat ruang";
    } finally {
      createBusy = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Ruang — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <p class="mono-label">Kompetisi Langsung</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Ruang</h1>
    </div>
    {#if canManage}
      <button class="btn-primary" on:click={() => (showCreate = !showCreate)}>＋ Buat ruang</button>
    {/if}
  </div>

  <div class="card mt-6">
    <h2 class="hud font-display text-lg font-bold">Gabung dengan kode</h2>
    <div class="mt-2 flex gap-2">
      <input
        class="input max-w-xs uppercase"
        placeholder="ABC123"
        bind:value={joinCode}
        maxlength="12"
      />
      <button
        class="btn-primary"
        on:click={joinByCode}
        disabled={joinLoading || joinCode.length < 4}
      >
        {joinLoading ? "Bergabung…" : "Gabung"}
      </button>
    </div>
    {#if joinError}<p class="alert-error mt-2">{joinError}</p>{/if}
  </div>

  {#if showCreate}
    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Ruang baru</h2>
      <div class="mt-3 grid gap-3 sm:grid-cols-3">
        <input class="input sm:col-span-2" placeholder="Nama ruang" bind:value={newRoom.name} />
        <input class="input" type="number" min="2" bind:value={newRoom.max_participants} />
      </div>
      <label class="mt-3 flex items-center gap-2 text-sm">
        <input type="checkbox" bind:checked={newRoom.is_public} /> Ruang publik
      </label>
      <button
        class="btn-primary mt-4"
        on:click={createRoom}
        disabled={createBusy || newRoom.name.length < 2}>{createBusy ? "Membuat…" : "Buat"}</button
      >
    </div>
  {/if}

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  {#if loading}
    <p class="mt-6 muted">Memuat ruang…</p>
  {:else if rooms.length === 0}
    <div class="card mt-6 text-center"><p class="muted">Belum ada ruang tersedia.</p></div>
  {:else}
    <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each pagedRooms as room}
        <a href={`/rooms/${room.id}`} class="card lift block hover:border-primary">
          <div class="flex items-center justify-between">
            <h2 class="font-display text-lg font-bold">{room.name}</h2>
            <span
              class="badge"
              class:badge-mint={room.status === "open"}
              class:badge-neutral={room.status !== "open"}>{statusLabel(room.status)}</span
            >
          </div>
          <p class="mt-2 font-mono text-sm muted">Kode: {room.code}</p>
        </a>
      {/each}
    </div>
    <Pagination
      page={currentPage}
      pageSize={PAGE_SIZE}
      total={rooms.length}
      {loading}
      label="ruang"
      onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
      onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
    />
  {/if}
</div>
