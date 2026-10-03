<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api } from "$lib/api/client";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import { adminNav } from "$lib/data/role-nav";
  import { relativeTime } from "$lib/utils/format";
  import { reveal } from "$lib/actions/reveal";
  import type { User, Reward } from "$lib/types";

  // Redirect once auth resolves (a mount-only check could fire too early and
  // leave the admin panel visible to a non-admin mid-load).
  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  // The hub shows every admin section except the "Ringkasan" entry (this page).
  const links = adminNav.filter((l) => l.href !== "/admin");

  interface AdminWithdrawal {
    id: string;
    user_id: string;
    amount: number;
    status: string;
    created_at: string;
  }
  interface AuditRow {
    id: string;
    action: string;
    actor_id?: string | null;
    created_at: string;
  }
  interface NegativeBalance {
    account_id: string;
    user_id: string;
    cached_balance: number;
  }

  // Live operational state, composed from the existing admin endpoints.
  let users: User[] = [];
  let withdrawals: AdminWithdrawal[] = [];
  let rewards: Reward[] = [];
  let negative: NegativeBalance[] = [];
  let recentAudit: AuditRow[] = [];
  let loading = true;
  // Which endpoint groups failed to load. An ops dashboard must never present a
  // failed fetch as "0 pending / balanced": that reads as "all healthy".
  let unavailable: string[] = [];

  onMount(async () => {
    const failures: string[] = [];
    const safe = async <T,>(p: Promise<T>, fallback: T, label: string): Promise<T> => {
      try {
        return await p;
      } catch {
        failures.push(label);
        return fallback;
      }
    };
    const [u, w, r, n, a] = await Promise.all([
      safe(api.get<User[]>("/admin/users?limit=200"), [], "pengguna"),
      safe(api.get<AdminWithdrawal[]>("/admin/withdrawals?limit=200"), [], "penarikan"),
      safe(api.get<Reward[]>("/admin/rewards?limit=200"), [], "hadiah"),
      safe(api.get<NegativeBalance[]>("/admin/ledger/negative?limit=200"), [], "buku besar"),
      safe(api.get<AuditRow[]>("/admin/audit-logs?limit=6"), [], "log audit"),
    ]);
    users = u;
    withdrawals = w;
    rewards = r;
    negative = n;
    recentAudit = a;
    unavailable = failures;
    loading = false;
  });

  // --- derived operational signals -------------------------------------------
  // A withdrawal is "awaiting action" while it is anywhere in the
  // requested → approved → submitted pipeline (matching the wallet view and the
  // withdrawals admin page). There is no bare "pending" status.
  const PENDING_WITHDRAWAL_STATUSES = ["requested", "approved", "submitted"];
  $: pendingWithdrawals = withdrawals.filter((w) =>
    PENDING_WITHDRAWAL_STATUSES.includes(w.status),
  ).length;
  $: failedRewards = rewards.filter((r) => r.status === "failed").length;
  $: pendingRewards = rewards.filter((r) => r.status === "pending").length;
  $: activeUsers = users.filter((u) => u.is_active).length;
  $: teacherCount = users.filter((u) => u.roles?.includes("teacher")).length;
  $: needsAttention = pendingWithdrawals + failedRewards + pendingRewards + negative.length;

  interface AdminLink {
    href: string;
    label: string;
    desc?: string;
    icon: string;
    status: string | null;
    tone: "mint" | "amber" | "indigo" | "neutral" | "danger";
    alert: boolean;
  }

  const toneClass: Record<AdminLink["tone"], string> = {
    mint: "badge-mint",
    amber: "badge-amber",
    indigo: "badge-indigo",
    neutral: "badge-neutral",
    danger: "badge-magenta",
  };

  // Attach a live status to the relevant nav entries (best-effort by href).
  // When the underlying fetch failed, the card must not claim a healthy
  // state: report it as unavailable instead.
  function statusFor(href: string): {
    status: string | null;
    tone: AdminLink["tone"];
    alert: boolean;
  } {
    const failed = (...labels: string[]) => labels.some((l) => unavailable.includes(l));
    switch (href) {
      case "/admin/users":
        if (failed("pengguna"))
          return { status: "Data tak tersedia", tone: "neutral", alert: false };
        return { status: `${activeUsers} aktif`, tone: "mint", alert: false };
      case "/admin/withdrawals":
        if (failed("penarikan"))
          return { status: "Data tak tersedia", tone: "neutral", alert: false };
        return pendingWithdrawals
          ? { status: `${pendingWithdrawals} menunggu`, tone: "amber", alert: true }
          : { status: "Tidak ada antrean", tone: "neutral", alert: false };
      case "/admin/rewards":
        if (failed("hadiah")) return { status: "Data tak tersedia", tone: "neutral", alert: false };
        return failedRewards
          ? { status: `${failedRewards} gagal`, tone: "danger", alert: true }
          : pendingRewards
            ? { status: `${pendingRewards} tertunda`, tone: "amber", alert: true }
            : { status: "Semua terkirim", tone: "mint", alert: false };
      case "/admin/ledger":
        if (failed("buku besar"))
          return { status: "Data tak tersedia", tone: "neutral", alert: false };
        return negative.length
          ? { status: `${negative.length} saldo negatif`, tone: "danger", alert: true }
          : { status: "Seimbang", tone: "mint", alert: false };
      case "/admin/moderation":
        return { status: null, tone: "neutral", alert: false };
      default:
        return { status: null, tone: "neutral", alert: false };
    }
  }

  $: decorated = links.map((l) => {
    // Reference the live signals so this recomputes once they load (Svelte
    // cannot see through the statusFor() call).
    void activeUsers;
    void pendingWithdrawals;
    void failedRewards;
    void pendingRewards;
    void negative;
    void unavailable;
    const s = statusFor(l.href);
    return { ...l, status: s.status, tone: s.tone, alert: s.alert } satisfies AdminLink;
  });
</script>

<svelte:head><title>Admin | QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Admin</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Operasional platform</h1>
      <p class="mt-2 muted">Kelola pengguna, hadiah, blockchain, dan audit.</p>
    </div>
    {#if !loading && needsAttention > 0}
      <span class="badge badge-amber text-xs">
        <Icon name="triangle-exclamation" size="11px" />
        {needsAttention} item butuh perhatian
      </span>
    {/if}
  </div>

  {#if loading}
    <div class="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {#each Array(4) as _}<div class="skeleton h-24"></div>{/each}
    </div>
    <div class="mt-8 grid gap-5 sm:grid-cols-2">
      {#each Array(4) as _}<div class="skeleton h-32"></div>{/each}
    </div>
  {:else}
    {#if unavailable.length}
      <div class="alert-warning mt-6 flex items-start gap-3" role="alert" aria-live="assertive">
        <Icon name="triangle-exclamation" class="mt-0.5 flex-none" size="14px" />
        <p class="text-sm">
          Sebagian data operasional gagal dimuat ({unavailable.join(", ")}). Angka di bawah bisa
          belum lengkap: jangan anggap sistem sehat hanya dari tampilan ini.
        </p>
      </div>
    {/if}
    <!-- Operational metrics -->
    <div class="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Pengguna aktif</p>
        <p class="mt-1 font-display text-3xl font-bold" data-role="active-users">{activeUsers}</p>
        <p class="text-[10px] muted">dari {users.length} · {teacherCount} guru</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Withdrawal menunggu</p>
        <p
          class="mt-1 font-display text-3xl font-bold text-highlight"
          data-role="pending-withdrawals"
        >
          {pendingWithdrawals}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Hadiah gagal</p>
        <p class="mt-1 font-display text-3xl font-bold" class:text-danger={failedRewards > 0}>
          {failedRewards}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Saldo negatif</p>
        <p class="mt-1 font-display text-3xl font-bold" class:text-danger={negative.length > 0}>
          {negative.length}
        </p>
      </div>
    </div>

    <!-- Health warnings -->
    {#if failedRewards > 0 || negative.length > 0}
      <div class="mt-4 card border-amber-500/40">
        <div class="flex items-center gap-2 text-amber-400">
          <Icon name="triangle-exclamation" size="14px" />
          <p class="font-semibold text-sm">Perlu tindakan</p>
        </div>
        <ul class="mt-2 space-y-1 text-sm">
          {#if failedRewards > 0}
            <li class="flex items-center justify-between gap-2">
              <span class="muted">{failedRewards} hadiah gagal dikirim ke chain</span>
              <a href="/admin/rewards" class="text-xs text-primary">Coba lagi →</a>
            </li>
          {/if}
          {#if negative.length > 0}
            <li class="flex items-center justify-between gap-2">
              <span class="muted"
                >{negative.length} akun dengan saldo OPT negatif (utang clawback)</span
              >
              <a href="/admin/ledger" class="text-xs text-primary">Periksa →</a>
            </li>
          {/if}
        </ul>
      </div>
    {/if}

    <!-- Module grid with live status -->
    <div class="mt-8 grid gap-5 sm:grid-cols-2">
      {#each decorated as l, i (l.href)}
        <a
          href={l.href}
          use:reveal={{ delay: i * 40 }}
          class="card lift block"
          data-module={l.href}
        >
          <div class="flex items-start justify-between">
            <span class="tile h-11 w-11">
              <Icon name={l.icon} size="18px" />
            </span>
            {#if l.status}
              <span class="badge {toneClass[l.tone]}">
                {#if l.alert}<Icon name="triangle-exclamation" size="9px" />{/if}
                {l.status}
              </span>
            {/if}
          </div>
          <h2 class="mt-3 font-display text-lg font-bold">{l.label}</h2>
          <p class="mt-1 text-sm muted">{l.desc}</p>
        </a>
      {/each}
    </div>

    <!-- Recent audit -->
    {#if recentAudit.length}
      <div class="mt-8">
        <div class="flex items-center justify-between">
          <h2 class="font-display text-lg font-bold">Aktivitas terbaru</h2>
          <a href="/admin/audit" class="text-xs text-primary"
            >Lihat semua <Icon name="arrow-right" size="10px" /></a
          >
        </div>
        <ul class="mt-3 card !p-0 divide-y">
          {#each recentAudit as row (row.id)}
            <li class="flex items-center justify-between gap-3 px-5 py-3 text-sm">
              <span class="flex items-center gap-2 min-w-0">
                <Icon name="clipboard-list" size="11px" class="text-primary flex-none" />
                <span class="mono truncate">{row.action}</span>
              </span>
              <span class="text-xs muted flex-none">{relativeTime(row.created_at)}</span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  {/if}
</div>
