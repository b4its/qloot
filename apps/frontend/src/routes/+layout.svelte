<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { auth, hasRole } from "$lib/stores/auth";
  import { notifications } from "$lib/stores/notifications";
  import ThemeToggle from "$lib/components/ThemeToggle.svelte";
  import Icon from "$lib/components/Icon.svelte";

  onMount(() => {
    auth.load();
    notifications.refresh();
  });

  const primaryNav = [
    { href: "/courses", label: "Kursus" },
    { href: "/paths", label: "Jalur Belajar" },
    { href: "/community", label: "Komunitas" },
    { href: "/business", label: "Untuk Bisnis" },
  ];

  const appNav = [
    { href: "/dashboard", label: "Dashboard", icon: "gauge-high" },
    { href: "/learning", label: "Learning", icon: "book-open-reader" },
    { href: "/rooms", label: "Rooms", icon: "bullseye" },
    { href: "/exams", label: "Exams", icon: "file-pen" },
    { href: "/quests", label: "Quests", icon: "trophy" },
    { href: "/tasks", label: "Tasks", icon: "list-check" },
    { href: "/ranking", label: "Ranking", icon: "ranking-star" },
    { href: "/wallet", label: "Wallet", icon: "gem" },
    { href: "/badges", label: "Badges", icon: "medal" },
    { href: "/career", label: "Career", icon: "compass" },
    { href: "/assistant", label: "AI Assistant", icon: "robot" },
  ];

  let mobileOpen = false;
  let searchOpen = false;
  $: user = $auth.user;
  $: path = $page.url.pathname;
  $: isAppArea =
    appNav.some((n) => path.startsWith(n.href)) ||
    path.startsWith("/profile") ||
    path.startsWith("/admin") ||
    path.startsWith("/teacher");

  async function logout() {
    await auth.logout();
    notifications.clear();
    window.location.href = "/";
  }

  const tickerItems = [
    "KELAS BARU · Desain Sistem untuk Web3 · Mulai 1 Okt · Kuota tersisa 24",
    "SERTIFIKAT DIGITAL · Kredensial dapat diverifikasi · Gratis untuk semua kelas",
    "KOMUNITAS · 12.000+ pelajar aktif · Sesi tanya-jawab setiap Rabu",
    "JALUR BELAJAR BARU · AI Engineer · 6 kursus · 16 minggu",
  ];
</script>

<div class="relative min-h-screen">
  <!-- ================= NAV ================= -->
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

      <!-- primary marketing nav -->
      <nav class="hidden items-center gap-1 md:flex" aria-label="Navigasi utama">
        {#each primaryNav as item}
          <a
            href={item.href}
            class="rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors hover:bg-ink/5"
            class:text-primary={path.startsWith(item.href)}
          >
            {item.label}
          </a>
        {/each}
      </nav>

      <div class="ml-auto flex items-center gap-2">
        <button
          class="btn-icon"
          aria-label="Cari kursus"
          on:click={() => (searchOpen = !searchOpen)}
        >
          <Icon name="magnifying-glass" size="14px" />
        </button>
        <ThemeToggle />

        {#if user}
          <a href="/notifications" class="btn-icon relative" aria-label="Notifikasi">
            <Icon name="bell" size="14px" />
            {#if $notifications > 0}
              <span
                class="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-tertiary px-1 text-[10px] font-bold text-white"
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
        <div class="mx-auto flex max-w-7xl items-center gap-3">
          <Icon name="magnifying-glass" class="muted" />
          <input
            class="input !border-0 !bg-transparent !px-0"
            placeholder="Cari kursus, jalur belajar, atau mentor…"
            aria-label="Cari"
          />
          <button class="btn-ghost" on:click={() => (searchOpen = false)}>Tutup</button>
        </div>
      </div>
    {/if}

    <!-- app sub-nav -->
    {#if isAppArea}
      <div class="border-t">
        <div class="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 py-1.5 sm:px-6">
          {#each appNav as item}
            <a
              href={item.href}
              class="flex flex-none items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors hover:bg-ink/5"
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
            class="block rounded-lg px-3 py-2 text-sm"
            on:click={() => (mobileOpen = false)}>{item.label}</a
          >
        {/each}
        <div class="my-2 border-t"></div>
        {#each appNav as item}
          <a
            href={item.href}
            class="block rounded-lg px-3 py-2 text-sm"
            on:click={() => (mobileOpen = false)}
          >
            <Icon name={item.icon} size="12px" class="mr-2" />{item.label}
          </a>
        {/each}
        {#if hasRole(user, "teacher")}
          <a href="/teacher" class="block rounded-lg px-3 py-2 text-sm">Panel Guru</a>
        {/if}
        {#if hasRole(user, "admin")}
          <a href="/admin" class="block rounded-lg px-3 py-2 text-sm">Admin</a>
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
  <footer class="mt-16 border-t border-white/5 bg-[#0A0A0C] text-white">
    <div class="mx-auto max-w-7xl px-4 py-14 sm:px-6">
      <div class="grid gap-10 lg:grid-cols-5">
        <div class="lg:col-span-2">
          <div class="flex items-center gap-2.5">
            <span
              class="grid h-9 w-9 place-items-center rounded-xl"
              style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
            >
              <Icon name="graduation-cap" size="16px" />
            </span>
            <span class="font-display text-lg font-bold">QLoot</span>
          </div>
          <p class="mt-4 max-w-sm text-sm text-white/60">
            Platform belajar gamifikasi dengan AI & teknologi on-chain. Kursus, jalur belajar,
            sertifikat digital, dan komunitas dalam satu tempat.
          </p>
          <div class="mt-5 flex max-w-sm items-center gap-2">
            <input
              class="input !border-white/10 !bg-white/5 text-white placeholder:text-white/40"
              placeholder="Email kamu untuk info kelas baru"
              aria-label="Email"
            />
            <button class="btn-primary flex-none" aria-label="Langganan buletin">
              <Icon name="paper-plane" size="13px" />
            </button>
          </div>
        </div>

        <div>
          <p class="mono-label !text-white/40">Belajar</p>
          <ul class="mt-3 space-y-2 text-sm text-white/70">
            <li><a class="hover:text-white" href="/courses">Katalog Kursus</a></li>
            <li><a class="hover:text-white" href="/paths">Jalur Belajar</a></li>
            <li><a class="hover:text-white" href="/community">Komunitas</a></li>
            <li><a class="hover:text-white" href="/career">Panduan Karier</a></li>
          </ul>
        </div>

        <div>
          <p class="mono-label !text-white/40">Perusahaan</p>
          <ul class="mt-3 space-y-2 text-sm text-white/70">
            <li><a class="hover:text-white" href="/about">Tentang</a></li>
            <li><a class="hover:text-white" href="/business">Untuk Bisnis</a></li>
            <li><a class="hover:text-white" href="/careers">Karier</a></li>
            <li><a class="hover:text-white" href="/blog">Blog</a></li>
          </ul>
        </div>

        <div>
          <p class="mono-label !text-white/40">Sumber Daya</p>
          <ul class="mt-3 space-y-2 text-sm text-white/70">
            <li><a class="hover:text-white" href="/faq">FAQ</a></li>
            <li><a class="hover:text-white" href="/certificates">Sertifikat</a></li>
            <li>
              <a class="hover:text-white" href="/docs" target="_blank" rel="noopener"
                >Dokumentasi API</a
              >
            </li>
            <li><a class="hover:text-white" href="/legal">Legal & Privasi</a></li>
          </ul>
        </div>
      </div>

      <div
        class="mt-12 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-6 text-xs text-white/50 sm:flex-row"
      >
        <p>© {new Date().getFullYear()} QLoot. Dibuat untuk pengalaman belajar yang lebih baik.</p>
        <div class="flex items-center gap-3">
          <a href="https://github.com" class="text-white/60 hover:text-white" aria-label="GitHub">
            <Icon name="github" set="brands" size="16px" />
          </a>
          <a href="https://x.com" class="text-white/60 hover:text-white" aria-label="X">
            <Icon name="x-twitter" set="brands" size="16px" />
          </a>
          <a
            href="https://linkedin.com"
            class="text-white/60 hover:text-white"
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
