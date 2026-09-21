<script lang="ts">
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { auth, hasRole } from "$lib/stores/auth";
  import { notifications } from "$lib/stores/notifications";
  import { opc } from "$lib/stores/opc";
  import ThemeToggle from "$lib/components/ThemeToggle.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import OpcChip from "$lib/components/OpcChip.svelte";
  import { API_BASE } from "$lib/api/client";

  const primaryNav = [
    { href: "/courses", label: "Pelajaran" },
    { href: "/paths", label: "Jalur Belajar" },
    { href: "/community", label: "Komunitas" },
    { href: "/about", label: "Tentang" },
  ];

  const appNav = [
    { href: "/dashboard", label: "Dashboard", icon: "gauge-high" },
    { href: "/learning", label: "Pelajaran Saya", icon: "book-open-reader" },
    { href: "/rooms", label: "Ruang", icon: "bullseye" },
    { href: "/exams", label: "Ujian", icon: "file-pen" },
    { href: "/quests", label: "Quest", icon: "trophy" },
    { href: "/tasks", label: "Tugas", icon: "list-check" },
    { href: "/ranking", label: "Peringkat", icon: "ranking-star" },
    { href: "/badges", label: "Badge", icon: "medal" },
    { href: "/career", label: "Karier", icon: "compass" },
    { href: "/assistant", label: "Asisten Qlo", icon: "robot" },
  ];

  let mobileOpen = false;
  let searchOpen = false;
  let searchQuery = "";
  $: user = $auth.user;
  $: path = $page.url.pathname;
  $: isAppArea =
    appNav.some((n) => path.startsWith(n.href)) ||
    path.startsWith("/profile") ||
    path.startsWith("/admin") ||
    path.startsWith("/teacher");

  function submitSearch() {
    const q = searchQuery.trim();
    searchOpen = false;
    goto(`/courses${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  }

  let newsletterEmail = "";
  let newsletterMsg = "";
  function subscribe() {
    // Simulated newsletter signup (no email is actually sent).
    newsletterMsg = `Terima kasih! ${newsletterEmail} akan menerima info kelas baru.`;
    newsletterEmail = "";
  }

  async function logout() {
    await auth.logout();
    notifications.clear();
    opc.reset();
    window.location.href = "/";
  }

  const tickerItems = [
    "PELAJARAN BARU · Matematika 1A · Ditargetkan untuk Kelas 1A (IPA)",
    "SERTIFIKAT DIGITAL · Kredensial dengan ID unik & tautan verifikasi",
    "KOMUNITAS · 12.000+ pelajar aktif · Sesi tanya-jawab setiap Rabu",
    "OPC · OryphemCoin untuk setiap pencapaian belajar · Dapat dilacak",
  ];
</script>

<div class="relative min-h-screen">
  <!-- ================= NAV ================= -->
  <header class="cyber-rule sticky top-0 z-40 border-b glass">
    <div class="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
      <a href="/" class="flex items-center gap-2.5">
        <span class="brand-mark grid h-9 w-9 place-items-center rounded-sm glow-yellow">
          <Icon name="graduation-cap" size="16px" />
        </span>
        <span class="font-display text-lg font-bold uppercase tracking-tight">QLoot</span>
      </a>

      <!-- primary marketing nav -->
      <nav class="hidden items-center gap-1 md:flex" aria-label="Navigasi utama">
        {#each primaryNav as item}
          <a
            href={item.href}
            class="hud rounded-sm px-3.5 py-1.5 text-xs font-semibold transition-colors hover:bg-primary/10 hover:text-primary"
            class:text-primary={path.startsWith(item.href)}
          >
            {item.label}
          </a>
        {/each}
      </nav>

      <div class="ml-auto flex items-center gap-2">
        <button
          class="btn-icon"
          aria-label="Cari pelajaran"
          on:click={() => (searchOpen = !searchOpen)}
        >
          <Icon name="magnifying-glass" size="14px" />
        </button>
        <ThemeToggle />

        {#if user}
          <!-- OPC balance — visible for both students and teachers -->
          <OpcChip compact={false} />
          {#if user.class_code}
            <span class="badge badge-indigo hidden sm:inline-flex" title="Kelas kamu">
              <Icon name="chalkboard-user" size="9px" />
              {user.class_code}{user.class_type ? ` · ${user.class_type}` : ""}
            </span>
          {/if}
          <a href="/notifications" class="btn-icon relative" aria-label="Notifikasi">
            <Icon name="bell" size="14px" />
            {#if $notifications > 0}
              <span
                class="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-sm bg-danger px-1 text-[10px] font-bold text-white"
                >{$notifications}</span
              >
            {/if}
          </a>
          <a href="/dashboard" class="btn-icon" aria-label="Dashboard saya">
            <Icon name="user-astronaut" size="14px" />
          </a>
          <button class="btn-ghost hidden sm:inline-flex" on:click={logout}>Keluar</button>
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

    <!-- search drawer -->
    {#if searchOpen}
      <div class="border-t px-4 py-3 sm:px-6">
        <form
          class="mx-auto flex max-w-7xl items-center gap-3"
          on:submit|preventDefault={submitSearch}
        >
          <Icon name="magnifying-glass" class="muted" />
          <input
            class="input !border-0 !bg-transparent !px-0"
            placeholder="Cari pelajaran, kelas, atau guru…"
            aria-label="Cari"
            bind:value={searchQuery}
          />
          <button class="btn-primary !py-1.5" type="submit">Cari</button>
          <button class="btn-ghost" type="button" on:click={() => (searchOpen = false)}
            >Tutup</button
          >
        </form>
      </div>
    {/if}

    <!-- app sub-nav -->
    {#if isAppArea}
      <div class="border-t">
        <div class="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 py-1.5 sm:px-6">
          {#each appNav as item}
            <a
              href={item.href}
              class="flex flex-none items-center gap-1.5 rounded-sm px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition-colors hover:bg-primary/10 hover:text-primary"
              class:nav-active={path.startsWith(item.href)}
            >
              <Icon name={item.icon} size="12px" />
              {item.label}
            </a>
          {/each}
        </div>
      </div>
    {/if}

    <!-- mobile menu -->
    {#if mobileOpen}
      <nav class="border-t px-4 py-2 md:hidden">
        {#each primaryNav as item}
          <a
            href={item.href}
            class="hud block rounded-sm px-3 py-2 text-xs"
            on:click={() => (mobileOpen = false)}>{item.label}</a
          >
        {/each}
        <div class="my-2 border-t"></div>
        {#each appNav as item}
          <a
            href={item.href}
            class="block rounded-sm px-3 py-2 text-sm"
            on:click={() => (mobileOpen = false)}
          >
            <Icon name={item.icon} size="12px" class="mr-2" />{item.label}
          </a>
        {/each}
        {#if hasRole(user, "teacher")}
          <a href="/teacher" class="block rounded-sm px-3 py-2 text-sm">Panel Guru</a>
        {/if}
        {#if hasRole(user, "admin")}
          <a href="/admin" class="block rounded-sm px-3 py-2 text-sm">Admin</a>
        {/if}
      </nav>
    {/if}
  </header>

  <!-- ================= TICKER ================= -->
  <div class="ticker bg-surface">
    <div class="ticker-track py-2">
      {#each [0, 1] as _}
        {#each tickerItems as item}
          <span class="mono-label mx-8 inline-flex items-center gap-2">
            <Icon name="bolt" size="10px" class="text-secondary" />
            {item}
          </span>
        {/each}
      {/each}
    </div>
  </div>

  <!-- ================= MAIN ================= -->
  <main class="relative z-10">
    <slot />
  </main>

  <!-- ================= FOOTER ================= -->
  <footer class="cyber-rule mt-16 border-t border-white/5 bg-[#05060A] text-white">
    <div class="mx-auto max-w-7xl px-4 py-14 sm:px-6">
      <div class="grid gap-10 lg:grid-cols-5">
        <div class="lg:col-span-2">
          <div class="flex items-center gap-2.5">
            <span class="brand-mark grid h-9 w-9 place-items-center rounded-sm">
              <Icon name="graduation-cap" size="16px" />
            </span>
            <span class="font-display text-lg font-bold uppercase">QLoot</span>
          </div>
          <p class="mt-4 max-w-sm text-sm text-white/60">
            Platform e-learning kelas dengan gamifikasi, AI, dan teknologi on-chain. Pelajaran per
            kelas, sertifikat digital, dan komunitas dalam satu tempat.
          </p>
          <div class="mt-5 max-w-sm">
            <form class="flex items-center gap-2" on:submit|preventDefault={subscribe}>
              <input
                class="input !border-white/10 !bg-surface/5 text-white placeholder:text-white/40"
                placeholder="Email kamu untuk info kelas baru"
                aria-label="Email"
                type="email"
                bind:value={newsletterEmail}
                required
              />
              <button class="btn-primary flex-none" type="submit" aria-label="Langganan buletin">
                <Icon name="paper-plane" size="13px" />
              </button>
            </form>
            {#if newsletterMsg}
              <p class="mt-2 text-xs text-primary">{newsletterMsg}</p>
            {/if}
          </div>
        </div>

        <div>
          <p class="mono-label !text-primary">Belajar</p>
          <ul class="mt-3 space-y-2 text-sm text-white/70">
            <li>
              <a class="transition-colors hover:text-primary" href="/courses">Daftar Pelajaran</a>
            </li>
            <li><a class="transition-colors hover:text-primary" href="/paths">Jalur Belajar</a></li>
            <li><a class="transition-colors hover:text-primary" href="/community">Komunitas</a></li>
            <li>
              <a class="transition-colors hover:text-primary" href="/career">Panduan Karier</a>
            </li>
          </ul>
        </div>

        <div>
          <p class="mono-label !text-primary">Perusahaan</p>
          <ul class="mt-3 space-y-2 text-sm text-white/70">
            <li><a class="transition-colors hover:text-primary" href="/about">Tentang</a></li>
            <li>
              <a class="transition-colors hover:text-primary" href="/business">Untuk Bisnis</a>
            </li>
            <li><a class="transition-colors hover:text-primary" href="/careers">Karier</a></li>
            <li><a class="transition-colors hover:text-primary" href="/blog">Blog</a></li>
          </ul>
        </div>

        <div>
          <p class="mono-label !text-primary">Sumber Daya</p>
          <ul class="mt-3 space-y-2 text-sm text-white/70">
            <li><a class="transition-colors hover:text-primary" href="/faq">FAQ</a></li>
            <li>
              <a class="transition-colors hover:text-primary" href="/certificates">Sertifikat</a>
            </li>
            <li>
              <a
                class="transition-colors hover:text-primary"
                href={`${API_BASE}/docs`}
                target="_blank"
                rel="noopener">Dokumentasi API</a
              >
            </li>
            <li>
              <a class="transition-colors hover:text-primary" href="/legal">Legal & Privasi</a>
            </li>
          </ul>
        </div>
      </div>

      <div
        class="mt-12 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-6 text-xs text-white/50 sm:flex-row"
      >
        <p>© {new Date().getFullYear()} QLoot. Dibuat untuk pengalaman belajar yang lebih baik.</p>
        <div class="flex items-center gap-3">
          <a href="https://github.com" class="text-white/60 hover:text-primary" aria-label="GitHub">
            <Icon name="github" set="brands" size="16px" />
          </a>
          <a href="https://x.com" class="text-white/60 hover:text-primary" aria-label="X">
            <Icon name="x-twitter" set="brands" size="16px" />
          </a>
          <a
            href="https://linkedin.com"
            class="text-white/60 hover:text-primary"
            aria-label="LinkedIn"
          >
            <Icon name="linkedin" set="brands" size="16px" />
          </a>
          <span class="mono ml-2">ID · EN</span>
        </div>
      </div>
    </div>
  </footer>
</div>
