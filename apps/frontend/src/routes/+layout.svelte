<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { auth, hasRole } from "$lib/stores/auth";
  import ThemeToggle from "$lib/components/ThemeToggle.svelte";

  onMount(() => {
    auth.load();
  });

  const nav = [
    { href: "/learning", label: "Learning", icon: "📚" },
    { href: "/rooms", label: "Rooms", icon: "🎯" },
    { href: "/exams", label: "Exams", icon: "📝" },
    { href: "/quests", label: "Quests", icon: "🏆" },
    { href: "/tasks", label: "Tasks", icon: "✅" },
    { href: "/ranking", label: "Ranking", icon: "📊" },
    { href: "/wallet", label: "Wallet", icon: "💎" },
  ];

  let mobileOpen = false;
  $: user = $auth.user;

  async function logout() {
    await auth.logout();
    window.location.href = "/";
  }
</script>

<div class="min-h-screen">
  <header class="sticky top-0 z-30 border-b backdrop-blur" style="background-color: var(--surface)">
    <div class="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
      <a href="/" class="flex items-center gap-2 text-lg font-bold">
        <span
          class="grid h-8 w-8 place-items-center rounded-lg text-white"
          style="background-color: var(--primary)">Q</span
        >
        QLoot
      </a>

      <nav class="hidden items-center gap-1 md:flex">
        {#each nav as item}
          <a
            href={item.href}
            class="rounded-lg px-3 py-1.5 text-sm font-medium transition hover:bg-primary-50 dark:hover:bg-slate-800"
            class:text-primary-600={$page.url.pathname.startsWith(item.href)}
          >
            <span class="mr-1" aria-hidden="true">{item.icon}</span>{item.label}
          </a>
        {/each}
        {#if hasRole(user, "teacher")}
          <a
            href="/teacher"
            class="rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-primary-50 dark:hover:bg-slate-800"
            >🧑‍🏫 Teacher</a
          >
        {/if}
        {#if hasRole(user, "admin")}
          <a
            href="/admin"
            class="rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-primary-50 dark:hover:bg-slate-800"
            >⚙️ Admin</a
          >
        {/if}
      </nav>

      <div class="ml-auto flex items-center gap-2">
        <ThemeToggle />
        {#if user}
          <div class="hidden items-center gap-2 sm:flex">
            <a href="/profile" class="text-sm font-medium">{user.full_name}</a>
            <button class="btn-ghost" on:click={logout}>Logout</button>
          </div>
          <button
            class="btn-ghost md:hidden"
            aria-label="Menu"
            on:click={() => (mobileOpen = !mobileOpen)}>☰</button
          >
        {:else}
          <a href="/login" class="btn-ghost">Login</a>
          <a href="/register" class="btn-primary">Sign up</a>
        {/if}
      </div>
    </div>

    {#if mobileOpen}
      <nav class="border-t px-4 py-2 md:hidden">
        {#each nav as item}
          <a href={item.href} class="block rounded px-3 py-2 text-sm" on:click={() => (mobileOpen = false)}
            >{item.icon} {item.label}</a
          >
        {/each}
      </nav>
    {/if}
  </header>

  <main class="mx-auto max-w-7xl px-4 py-6">
    <slot />
  </main>

  <footer class="mt-12 border-t py-6 text-center text-xs muted">
    QLoot — gamified learning with AI &amp; blockchain · OryphemCoin (OPC)
  </footer>
</div>
