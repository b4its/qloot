<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { auth, hasRole } from "$lib/stores/auth";
  import { formatNumber } from "$lib/utils/format";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Icon from "$lib/components/Icon.svelte";

  interface RuntimeConfig {
    env: string;
    ai_provider: string;
    blockchain: string;
    dry_run: boolean;
    reward_ranks: number[];
    confirmations: number;
    opc_max_reward_per_tx: number;
    rate_limit_enabled: boolean;
    csrf_enabled: boolean;
    readiness_check_redis: boolean;
    readiness_check_storage: boolean;
    use_local_storage: boolean;
    session_ttl_seconds: number;
    platform_timezone: string;
  }

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  let config: RuntimeConfig | null = null;
  let error = "";
  let loading = true;
  let copied = "";

  async function load() {
    if (!hasRole($auth.user, "admin")) return;
    loading = true;
    error = "";
    try {
      config = await api.get<RuntimeConfig>("/admin/config");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat konfigurasi";
    } finally {
      loading = false;
    }
  }

  function humanTtl(seconds: number): string {
    if (!seconds) return "-";
    const hours = Math.floor(seconds / 3600);
    if (hours >= 24) return `${Math.round(hours / 24)} hari (${formatNumber(seconds)} dtk)`;
    if (hours >= 1) return `${hours} jam (${formatNumber(seconds)} dtk)`;
    return `${Math.round(seconds / 60)} menit`;
  }

  let copyError = "";
  async function copy(value: string, key: string) {
    copyError = "";
    try {
      await navigator.clipboard?.writeText(value);
      copied = key;
      setTimeout(() => (copied = ""), 1500);
    } catch {
      // Clipboard can be blocked (insecure context). Tell the admin rather than
      // leaving the button looking like it did nothing.
      copyError = "Tidak dapat menyalin ke clipboard. Salin manual dari nilai di layar.";
      setTimeout(() => (copyError = ""), 4000);
    }
  }

  const bool = (v: boolean) => (v ? "Aktif" : "Nonaktif");
  onMount(load);

  // --- status signaling ------------------------------------------------------
  $: isProduction = config?.env?.toLowerCase() === "production";
  $: dryRun = config?.dry_run ?? false;
  $: hardeners = config
    ? [config.rate_limit_enabled, config.csrf_enabled, !config.dry_run].filter(Boolean).length
    : 0;
</script>

<svelte:head><title>Konfigurasi | Admin | QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Sistem"
    title="Konfigurasi Runtime"
    subtitle="Ringkasan konfigurasi non-rahasia platform. Tidak ada nilai secret di halaman ini."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {error} />

  {#if loading}
    <div class="mt-6 skeleton h-52"></div>
  {:else if config}
    <!-- Status banner -->
    <div
      class="card mt-4 flex flex-wrap items-center gap-3 border {isProduction
        ? 'border-mint/40'
        : 'border-amber/40'}"
      data-role="env-banner"
    >
      <span class="tile-neutral h-10 w-10">
        <Icon
          name={isProduction ? "shield-halved" : "flask"}
          size="16px"
          class={isProduction ? "text-mint" : "text-highlight"}
        />
      </span>
      <div>
        <p class="font-semibold">
          Lingkungan: {config.env}
          {#if dryRun}<span class="badge badge-amber ml-2">Dry-run</span>{/if}
        </p>
        <p class="text-xs muted">
          {isProduction
            ? "Mode produksi: konfigurasi diamankan."
            : "Mode non-produksi: beberapa pengaman mungkin nonaktif."}
          · {hardeners}/3 pengaman inti aktif
        </p>
      </div>
    </div>

    <!-- AI & mode -->
    <section class="mt-6">
      <p class="mono-label">Mode & AI</p>
      <dl class="mt-2 grid gap-x-8 gap-y-3 sm:grid-cols-2">
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Lingkungan</dt>
          <dd class="font-medium">{config.env}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Provider AI</dt>
          <dd class="font-medium">{config.ai_provider}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Zona waktu platform</dt>
          <dd class="font-medium">{config.platform_timezone}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Peringkat hadiah</dt>
          <dd class="font-medium">
            {#each config.reward_ranks as r, i}<span class="badge badge-indigo mr-1">#{r}</span
              >{/each}
          </dd>
        </div>
      </dl>
    </section>

    <!-- Blockchain -->
    <section class="mt-6">
      <p class="mono-label">Blockchain</p>
      <dl class="mt-2 grid gap-x-8 gap-y-3 sm:grid-cols-2">
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Jaringan blockchain</dt>
          <dd class="font-medium">{config.blockchain}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Mode dry-run</dt>
          <dd class="font-medium" class:text-highlight={config.dry_run}>
            {bool(config.dry_run)}
          </dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Konfirmasi on-chain</dt>
          <dd class="font-medium">{config.confirmations}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Cap hadiah per transaksi</dt>
          <dd class="font-medium">{formatNumber(config.opc_max_reward_per_tx)}</dd>
        </div>
      </dl>
    </section>

    <!-- Security -->
    <section class="mt-6">
      <p class="mono-label">Keamanan</p>
      <dl class="mt-2 grid gap-x-8 gap-y-3 sm:grid-cols-2">
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Rate limiting</dt>
          <dd>
            <span
              class="badge"
              class:badge-mint={config.rate_limit_enabled}
              class:badge-neutral={!config.rate_limit_enabled}
            >
              {bool(config.rate_limit_enabled)}
            </span>
          </dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">CSRF token</dt>
          <dd>
            <span
              class="badge"
              class:badge-mint={config.csrf_enabled}
              class:badge-neutral={!config.csrf_enabled}
            >
              {bool(config.csrf_enabled)}
            </span>
          </dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Masa berlaku sesi</dt>
          <dd class="font-medium">{humanTtl(config.session_ttl_seconds)}</dd>
        </div>
      </dl>
    </section>

    <!-- Storage & readiness -->
    <section class="mt-6">
      <p class="mono-label">Storage & Readiness</p>
      <dl class="mt-2 grid gap-x-8 gap-y-3 sm:grid-cols-2">
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Storage lokal</dt>
          <dd class="font-medium">{bool(config.use_local_storage)}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Probe Redis</dt>
          <dd class="font-medium">{bool(config.readiness_check_redis)}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Probe storage</dt>
          <dd class="font-medium">{bool(config.readiness_check_storage)}</dd>
        </div>
      </dl>
    </section>

    <div class="mt-6 flex items-center gap-2">
      <button
        class="btn-ghost text-xs"
        on:click={() => config && copy(JSON.stringify(config, null, 2), "all")}
      >
        <Icon name={copied === "all" ? "check" : "copy"} size="11px" />
        {copied === "all" ? "Tersalin" : "Salin konfigurasi (JSON)"}
      </button>
    </div>
    {#if copyError}
      <p class="mt-2 text-xs text-danger" role="alert" aria-live="assertive">{copyError}</p>
    {/if}
  {/if}
</div>
