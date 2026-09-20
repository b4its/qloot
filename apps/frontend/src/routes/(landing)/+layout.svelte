<script lang="ts">
  import { onMount } from "svelte";
  import { auth } from "$lib/stores/auth";
  import { notifications } from "$lib/stores/notifications";
  import { opc } from "$lib/stores/opc";
  import ThemeToggle from "$lib/components/ThemeToggle.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import OpcChip from "$lib/components/OpcChip.svelte";

  // The landing page has its own chrome, independent from the app shell
  // (no ticker / app sub-nav). It is a one-page experience: every entry in
  // the nav is an in-page anchor to a section below.
  const anchors = [
    { id: "fitur", label: "Fitur" },
    { id: "kelas", label: "Kelas" },
    { id: "guru", label: "Guru" },
    { id: "sertifikat", label: "Sertifikat" },
    { id: "testimoni", label: "Testimoni" },
  ];

  let mobileOpen = false;
  $: user = $auth.user;

  onMount(() => {
    // Root layout already bootstraps stores on SPA navigations; this covers a
    // direct landing on `/` and keeps the header state fresh.
    auth.load();
    notifications.refresh();
    opc.refresh();
  });

  function goTo(id: string) {
    mobileOpen = false;
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function logout() {
    await auth.logout();
    notifications.clear();
    opc.reset();
    window.location.href = "/";
  }
</script>

<div class="relative min-h-screen">
  <!-- ================= LANDING NAV ================= -->
  <header class="sticky top-0 z-40 border-b glass">
    <div class="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
      <a href="/" class="flex items-center gap-2.5">
        <span
          class="grid h-9 w-9 place-items-center rounded-xl text-white"
          style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
        >
          <Icon name="graduation-cap" size="16px" />
        </span>
        <span class="font-display text-lg font-bold tracking-tight">QLoot</span>
      </a>

      <!-- in-page anchor nav -->
      <nav class="hidden items-center gap-1 md:flex" aria-label="Navigasi landing">
        {#each anchors as item}
          <button
            type="button"
            class="rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors hover:bg-ink/5"
            on:click={() => goTo(item.id)}
          >
            {item.label}
          </button>
        {/each}
      </nav>

      <div class="ml-auto flex items-center gap-2">
        <ThemeToggle />

        {#if user}
          <OpcChip compact={false} />
          <a href="/notifications" class="btn-icon relative" aria-label="Notifikasi">
            <Icon name="bell" size="14px" />
            {#if $notifications > 0}
              <span
                class="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-tertiary px-1 text-[10px] font-bold text-white"
                >{$notifications}</span
              >
            {/if}
          </a>
          <a href="/dashboard" class="btn-secondary hidden sm:inline-flex"
            ><Icon name="gauge-high" size="12px" /> Dashboard</a
          >
          <button
            class="btn-icon md:hidden"
            aria-label="Menu"
            aria-expanded={mobileOpen}
            on:click={() => (mobileOpen = !mobileOpen)}
          >
            <Icon name={mobileOpen ? "xmark" : "bars"} size="14px" />
          </button>
        {:else}
          <a href="/login" class="btn-ghost hidden sm:inline-flex">Masuk</a>
          <a href="/register" class="btn-primary">Daftar</a>
          <button
            class="btn-icon md:hidden"
            aria-label="Menu"
            aria-expanded={mobileOpen}
            on:click={() => (mobileOpen = !mobileOpen)}
          >
            <Icon name={mobileOpen ? "xmark" : "bars"} size="14px" />
          </button>
        {/if}
      </div>
    </div>

    <!-- mobile menu -->
    {#if mobileOpen}
      <nav class="border-t px-4 py-2 md:hidden">
        {#each anchors as item}
          <button
            type="button"
            class="block w-full rounded-lg px-3 py-2 text-left text-sm"
            on:click={() => goTo(item.id)}>{item.label}</button
          >
        {/each}
        <div class="my-2 border-t"></div>
        {#if user}
          <a href="/dashboard" class="block rounded-lg px-3 py-2 text-sm">Dashboard</a>
          <a href="/learning" class="block rounded-lg px-3 py-2 text-sm">Pelajaran Saya</a>
          <button class="block w-full rounded-lg px-3 py-2 text-left text-sm" on:click={logout}>
            Keluar
          </button>
        {:else}
          <a href="/login" class="block rounded-lg px-3 py-2 text-sm">Masuk</a>
          <a href="/register" class="block rounded-lg px-3 py-2 text-sm">Daftar</a>
        {/if}
      </nav>
    {/if}
  </header>

  <!-- ================= LANDING CONTENT ================= -->
  <main class="relative z-10">
    <slot />
  </main>

  <!-- ================= LANDING FOOTER ================= -->
  <footer class="mt-16 border-t border-white/5 bg-[#0A0A0C] text-white">
    <div class="mx-auto max-w-7xl px-4 py-14 sm:px-6">
      <div class="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
        <div class="flex items-center gap-2.5">
          <span
            class="grid h-9 w-9 place-items-center rounded-xl"
            style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
          >
            <Icon name="graduation-cap" size="16px" />
          </span>
          <span class="font-display text-lg font-bold">QLoot</span>
        </div>
        <nav
          class="flex flex-wrap gap-x-6 gap-y-2 text-sm text-white/70"
          aria-label="Navigasi footer"
        >
          {#each anchors as item}
            <button type="button" class="hover:text-white" on:click={() => goTo(item.id)}>
              {item.label}
            </button>
          {/each}
          <a class="hover:text-white" href="/about">Tentang</a>
          <a class="hover:text-white" href="/faq">FAQ</a>
        </nav>
      </div>

      <div
        class="mt-10 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-6 text-xs text-white/50 sm:flex-row"
      >
        <p>© {new Date().getFullYear()} QLoot. Dibuat untuk pengalaman belajar yang lebih baik.</p>
        <span class="mono">ID · EN</span>
      </div>
    </div>
  </footer>
</div>
