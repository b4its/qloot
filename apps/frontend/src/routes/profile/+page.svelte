<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api/client";
  import type { SessionInfo } from "$lib/types";
  import { auth } from "$lib/stores/auth";
  import { formatDate } from "$lib/utils/format";

  let sessions: SessionInfo[] = [];
  $: user = $auth.user;

  async function load() {
    sessions = await api.get<SessionInfo[]>("/auth/sessions");
  }

  async function revoke(id: string) {
    await api.delete(`/auth/sessions/${id}`);
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>Profile — QLoot</title></svelte:head>

{#if !user}
  <p class="muted">Please sign in.</p>
{:else}
  <h1 class="text-2xl font-bold">Profile</h1>
  <div class="card mt-4">
    <dl class="grid gap-3 sm:grid-cols-2">
      <div><dt class="text-sm muted">Name</dt><dd class="font-medium">{user.full_name}</dd></div>
      <div><dt class="text-sm muted">Email</dt><dd class="font-medium">{user.email}</dd></div>
      <div>
        <dt class="text-sm muted">Roles</dt>
        <dd class="flex gap-1">
          {#each user.roles as r}<span class="badge bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-100">{r}</span>{/each}
        </dd>
      </div>
      <div>
        <dt class="text-sm muted">On-chain reference</dt>
        <dd class="font-mono text-xs">{user.chain_user_ref.slice(0, 18)}…</dd>
      </div>
    </dl>
  </div>

  <div class="card mt-4">
    <h2 class="font-semibold">Active sessions</h2>
    <ul class="mt-2 space-y-2 text-sm">
      {#each sessions as s}
        <li class="flex items-center justify-between">
          <span>
            <span class="muted">{s.user_agent ?? "Unknown device"}</span>
            <span class="block text-xs muted">Since {formatDate(s.created_at)}</span>
          </span>
          <button class="btn-ghost" on:click={() => revoke(s.id)}>Revoke</button>
        </li>
      {/each}
    </ul>
  </div>
{/if}
