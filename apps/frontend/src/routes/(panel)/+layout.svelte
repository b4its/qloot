<script lang="ts">
  /**
   * Dedicated shell for the /admin and /teacher panels. This group is
   * intentionally SEPARATE from the public (site) and (landing) groups: it has
   * its own chrome (sidebar + topbar), its own role guard, and never renders the
   * marketing nav, the ticker, or the marketing footer.
   */
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { auth, hasRole } from "$lib/stores/auth";
  import { notifications } from "$lib/stores/notifications";
  import { opt } from "$lib/stores/opt";
  import ThemeToggle from "$lib/components/ThemeToggle.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import OptChip from "$lib/components/OptChip.svelte";
  import { adminNav, teacherNav } from "$lib/data/role-nav";

  let sidebarOpen = false;
  $: user = $auth.user;
  $: path = $page.url.pathname;
  $: isAdminArea = path.startsWith("/admin");
  $: isTeacherArea = path.startsWith("/teacher");
  $: areaLabel = isAdminArea ? "Admin" : "Guru";
  $: areaIcon = isAdminArea ? "shield-halved" : "chalkboard-user";
  $: nav = isAdminArea ? adminNav : isTeacherArea ? teacherNav : [];

  // Role guard per sub-area. Admin always passes `hasRole` (see auth store), so
  // an admin may view the teacher panel too.
  $: if (!$auth.loading && user) {
    if (isAdminArea && !hasRole(user, "admin")) goto("/login");
    else if (isTeacherArea && !hasRole(user, "teacher")) goto("/login");
  }

  // Highlight the most specific matching item (so /teacher/subjects/new lights
  // up /teacher/subjects, not /teacher).
  function isActive(href: string): boolean {
    if (href === "/admin" || href === "/teacher") return path === href;
    return path === href || path.startsWith(`${href}/`);
  }

  async function logout() {
    await auth.logout();
    notifications.clear();
    opt.reset();
    window.location.href = "/";
  }
</script>

<div class="relative min-h-screen lg:grid lg:grid-cols-[264px_1fr]">
  <!-- ============ SIDEBAR (desktop) ============ -->
  <aside class="panel-sidebar hidden border-r lg:flex lg:flex-col">
    <a href="/" class="flex items-center gap-2.5 px-5 py-4">
      <span class="brand-mark grid h-9 w-9 place-items-center rounded-sm">
        <Icon name="graduation-cap" size="16px" />
      </span>
      <span class="flex flex-col leading-tight">
        <span class="font-display text-base font-bold uppercase tracking-tight">QLoot</span>
        <span class="mono-label flex items-center gap-1"
          ><Icon name={areaIcon} size="9px" /> Panel {areaLabel}</span
        >
      </span>
    </a>

    <nav
      class="flex-1 space-y-1 overflow-y-auto px-3 py-2"
      aria-label={`Navigasi panel ${areaLabel}`}
    >
      {#each nav as item}
        <a
          href={item.href}
          class="panel-nav-item"
          class:panel-nav-active={isActive(item.href)}
          aria-current={isActive(item.href) ? "page" : undefined}
        >
          <Icon name={item.icon} size="13px" />
          <span class="flex-1">{item.label}</span>
        </a>
      {/each}
    </nav>

    <div class="border-t p-3">
      <a href="/dashboard" class="panel-nav-item">
        <Icon name="arrow-left-from-bracket" size="13px" />
        <span class="flex-1">Kembali ke aplikasi</span>
      </a>
    </div>
  </aside>

  <div class="flex min-h-screen flex-col">
    <!-- ============ TOPBAR ============ -->
    <header class="sticky top-0 z-30 border-b glass">
      <div class="flex items-center gap-3 px-4 py-3 sm:px-6">
        <button
          class="btn-icon lg:hidden"
          aria-label="Buka menu panel"
          aria-expanded={sidebarOpen}
          on:click={() => (sidebarOpen = !sidebarOpen)}
        >
          <Icon name={sidebarOpen ? "xmark" : "bars"} size="14px" />
        </button>
        <span class="mono-label flex items-center gap-1.5"
          ><Icon name={areaIcon} size="11px" /> Panel {areaLabel}</span
        >

        <div class="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {#if user}
            <OptChip compact />
            <a href="/notifications" class="btn-icon relative" aria-label="Notifikasi">
              <Icon name="bell" size="14px" />
              {#if $notifications > 0}
                <span
                  class="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-sm bg-danger px-1 text-[10px] font-bold text-white"
                  >{$notifications}</span
                >
              {/if}
            </a>
            <a href="/profile" class="btn-icon" aria-label="Profil saya">
              <Icon name="user-astronaut" size="14px" />
            </a>
            <button class="btn-ghost hidden sm:inline-flex" on:click={logout}>Keluar</button>
          {/if}
        </div>
      </div>

      <!-- mobile nav drawer -->
      {#if sidebarOpen}
        <nav class="border-t px-3 py-2 lg:hidden" aria-label="Navigasi panel (mobile)">
          {#each nav as item}
            <a
              href={item.href}
              class="panel-nav-item"
              class:panel-nav-active={isActive(item.href)}
              on:click={() => (sidebarOpen = false)}
            >
              <Icon name={item.icon} size="13px" />
              <span class="flex-1">{item.label}</span>
            </a>
          {/each}
          <div class="my-2 border-t"></div>
          <a href="/dashboard" class="panel-nav-item" on:click={() => (sidebarOpen = false)}>
            <Icon name="arrow-left-from-bracket" size="13px" />
            <span class="flex-1">Kembali ke aplikasi</span>
          </a>
        </nav>
      {/if}
    </header>

    <!-- ============ CONTENT ============ -->
    <main class="relative z-10 flex-1">
      <slot />
    </main>
  </div>
</div>
