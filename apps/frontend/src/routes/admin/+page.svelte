<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { auth, hasRole } from "$lib/stores/auth";

  onMount(() => {
    if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");
  });

  const links = [
    { href: "/admin/blockchain", label: "Blockchain", desc: "Status, transactions, pause/unpause", icon: "⛓️" },
    { href: "/admin/rewards", label: "Rewards", desc: "Monitor, retry and cancel reward allocations", icon: "💎" },
    { href: "/admin/users", label: "Users", desc: "Manage roles and accounts", icon: "👥" },
    { href: "/admin/audit", label: "Audit log", desc: "Every privileged action", icon: "📜" },
  ];
</script>

<svelte:head><title>Admin — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Admin</h1>
<p class="mt-1 muted">Operate the platform: users, rewards, blockchain and audit.</p>

<div class="mt-6 grid gap-4 sm:grid-cols-2">
  {#each links as l}
    <a href={l.href} class="card block transition hover:border-primary-400">
      <div class="text-2xl" aria-hidden="true">{l.icon}</div>
      <h2 class="mt-1 font-semibold">{l.label}</h2>
      <p class="text-sm muted">{l.desc}</p>
    </a>
  {/each}
</div>
