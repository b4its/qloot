<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

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

  async function load() {
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

  const bool = (v: boolean) => (v ? "Aktif" : "Nonaktif");
  onMount(load);
</script>

<svelte:head><title>Konfigurasi — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Sistem"
    title="Konfigurasi Runtime"
    subtitle="Ringkasan konfigurasi non-rahasia platform. Tidak ada nilai secret di halaman ini."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {error} />

  <div class="card mt-6">
    {#if loading}
      <div class="grid gap-2 sm:grid-cols-2">
        {#each Array(6) as _}<div class="skeleton h-10"></div>{/each}
      </div>
    {:else if config}
      <dl class="grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Lingkungan</dt><dd class="font-medium">{config.env}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Provider AI</dt><dd class="font-medium">{config.ai_provider}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Jaringan blockchain</dt><dd class="font-medium">{config.blockchain}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Mode dry-run</dt><dd class="font-medium">{bool(config.dry_run)}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Konfirmasi on-chain</dt><dd class="font-medium">{config.confirmations}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Cap hadiah per transaksi</dt>
          <dd class="font-medium">{config.opc_max_reward_per_tx}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Peringkat hadiah</dt>
          <dd class="font-medium">{config.reward_ranks.join(", ")}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Zona waktu platform</dt><dd class="font-medium">{config.platform_timezone}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Rate limiting</dt><dd class="font-medium">{bool(config.rate_limit_enabled)}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">CSRF token</dt><dd class="font-medium">{bool(config.csrf_enabled)}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Probe Redis (readiness)</dt>
          <dd class="font-medium">{bool(config.readiness_check_redis)}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Probe storage (readiness)</dt>
          <dd class="font-medium">{bool(config.readiness_check_storage)}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Storage lokal</dt><dd class="font-medium">{bool(config.use_local_storage)}</dd>
        </div>
        <div class="flex items-center justify-between border-b py-2">
          <dt class="muted">Masa berlaku sesi (detik)</dt>
          <dd class="font-medium">{config.session_ttl_seconds}</dd>
        </div>
      </dl>
    {/if}
  </div>
</div>
