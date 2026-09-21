<script lang="ts">
  import { goto } from "$app/navigation";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import { adminNav } from "$lib/data/role-nav";

  // Redirect once auth resolves (a mount-only check could fire too early and
  // leave the admin panel visible to a non-admin mid-load).
  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  // The hub shows every admin section except the "Ringkasan" entry (this page).
  const links = adminNav.filter((l) => l.href !== "/admin");
</script>

<svelte:head><title>Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Admin</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Operasional platform</h1>
  <p class="mt-2 muted">Kelola pengguna, hadiah, blockchain, dan audit.</p>

  <div class="mt-8 grid gap-5 sm:grid-cols-2">
    {#each links as l}
      <a href={l.href} class="card lift block">
        <span class="tile h-11 w-11">
          <Icon name={l.icon} size="18px" />
        </span>
        <h2 class="mt-3 font-display text-lg font-bold">{l.label}</h2>
        <p class="mt-1 text-sm muted">{l.desc}</p>
      </a>
    {/each}
  </div>
</div>
