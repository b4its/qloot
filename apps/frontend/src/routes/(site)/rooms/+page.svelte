<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Room } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";

  let rooms: Room[] = [];
  let loading = true;
  let error = "";
  let joinCode = "";
  let joinError = "";
  let joinLoading = false;
  let showCreate = false;
  let newRoom = { name: "", max_participants: 100, is_public: true };

  $: canManage = hasRole($auth.user, "teacher");

  async function load() {
    loading = true;
    try {
      rooms = await api.get<Room[]>("/rooms");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load rooms";
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
      joinError = e instanceof ApiError ? e.message : "Could not join room";
    } finally {
      joinLoading = false;
    }
  }

  async function createRoom() {
    try {
      const room = await api.post<Room>("/rooms", newRoom);
      showCreate = false;
      window.location.href = `/rooms/${room.id}`;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Could not create room";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Rooms — QLoot</title></svelte:head>

<div class="flex flex-wrap items-center justify-between gap-3">
  <h1 class="text-2xl font-bold">Rooms</h1>
  {#if canManage}
    <button class="btn-primary" on:click={() => (showCreate = !showCreate)}>＋ Create room</button>
  {/if}
</div>

<div class="card mt-4">
  <h2 class="font-medium">Join with a code</h2>
  <div class="mt-2 flex gap-2">
    <input
      class="input max-w-xs uppercase"
      placeholder="ABC123"
      bind:value={joinCode}
      maxlength="12"
    />
    <button class="btn-primary" on:click={joinByCode} disabled={joinLoading || joinCode.length < 4}>
      {joinLoading ? "Joining…" : "Join"}
    </button>
  </div>
  {#if joinError}<p class="mt-2 text-sm text-tertiary">{joinError}</p>{/if}
</div>

{#if showCreate}
  <div class="card mt-4">
    <h2 class="font-medium">New room</h2>
    <div class="mt-3 grid gap-3 sm:grid-cols-3">
      <input class="input sm:col-span-2" placeholder="Room name" bind:value={newRoom.name} />
      <input class="input" type="number" min="2" bind:value={newRoom.max_participants} />
    </div>
    <label class="mt-3 flex items-center gap-2 text-sm">
      <input type="checkbox" bind:checked={newRoom.is_public} /> Public room
    </label>
    <button class="btn-primary mt-4" on:click={createRoom} disabled={newRoom.name.length < 2}
      >Create</button
    >
  </div>
{/if}

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-tertiary dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

{#if loading}
  <p class="mt-6 muted">Loading rooms…</p>
{:else if rooms.length === 0}
  <div class="card mt-6 text-center"><p class="muted">No rooms available.</p></div>
{:else}
  <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each rooms as room}
      <a href={`/rooms/${room.id}`} class="card block transition hover:border-primary">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">{room.name}</h2>
          <span
            class="badge"
            class:bg-green-100={room.status === "open"}
            class:text-secondary={room.status === "open"}
            class:tone-ink-soft={room.status !== "open"}
            class:dark:bg-surface={room.status !== "open"}>{room.status}</span
          >
        </div>
        <p class="mt-2 font-mono text-sm muted">Code: {room.code}</p>
      </a>
    {/each}
  </div>
{/if}
