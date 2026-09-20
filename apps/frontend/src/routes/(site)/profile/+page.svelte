<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api/client";
  import type { SessionInfo } from "$lib/types";
  import { auth } from "$lib/stores/auth";
  import { formatDate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";

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

<svelte:head><title>Profil — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  {#if !user}
    <p class="muted">Silakan masuk terlebih dahulu.</p>
  {:else}
    <p class="mono-label">Akun</p>
    <h1 class="mt-1 font-display text-3xl font-bold">Profil</h1>

    <div class="mt-6 grad-border">
      <div class="card">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <span
              class="grid h-14 w-14 place-items-center rounded-full font-display text-lg font-bold text-white"
              style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
            >
              {user.full_name
                .split(" ")
                .map((n) => n[0])
                .slice(0, 2)
                .join("")}
            </span>
            <div>
              <p class="font-display text-xl font-bold">{user.full_name}</p>
              <p class="text-sm muted">{user.email}</p>
            </div>
          </div>
          <WalletChip address={user.chain_user_ref} label="Wallet address" size={34} />
        </div>

        <div class="mt-5 flex flex-wrap gap-2 border-t pt-5">
          {#each user.roles as r}
            <span class="badge badge-indigo"><Icon name="user-tag" size="10px" /> {r}</span>
          {/each}
          {#if user.class_code}
            <span class="badge badge-mint">
              <Icon name="chalkboard-user" size="10px" /> Kelas {user.class_code}{user.class_type
                ? ` · ${user.class_type}`
                : ""}
            </span>
          {/if}
          <span class="badge badge-mint"><Icon name="circle-check" size="10px" /> Aktif</span>
        </div>
      </div>
    </div>

    <div class="mt-6 card">
      <div class="flex items-center justify-between">
        <h2 class="font-display font-bold">Sesi aktif</h2>
        <Icon name="shield-halved" size="14px" class="text-primary" />
      </div>
      <ul class="mt-3 divide-y">
        {#each sessions as s}
          <li class="flex items-center justify-between gap-4 py-3">
            <div class="flex items-center gap-3">
              <Icon name="display" size="14px" class="muted" />
              <div>
                <p class="text-sm">{s.user_agent?.slice(0, 48) ?? "Perangkat tidak dikenal"}</p>
                <p class="text-xs muted">Sejak {formatDate(s.created_at)}</p>
              </div>
            </div>
            <button class="btn-ghost" on:click={() => revoke(s.id)}>Cabut</button>
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</div>
