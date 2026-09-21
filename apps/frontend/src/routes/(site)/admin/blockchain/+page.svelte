<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { BlockchainStatus } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  let status: BlockchainStatus | null = null;
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";

  const links = [
    {
      href: "/admin/blockchain/transactions",
      label: "Transaksi",
      desc: "Semua transaksi on-chain dan status konfirmasinya",
      icon: "right-left",
    },
    {
      href: "/admin/blockchain/events",
      label: "Event",
      desc: "Event kontrak yang terindeks",
      icon: "bolt",
    },
  ];

  async function load() {
    loading = true;
    error = "";
    try {
      // Admin-only endpoint: includes contract/treasury addresses.
      status = await api.get<BlockchainStatus>("/blockchain/status/admin");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat data blockchain";
    } finally {
      loading = false;
    }
  }

  async function control(action: "pause" | "unpause") {
    error = "";
    message = "";
    busy = action;
    try {
      await api.post(`/admin/blockchain/${action}`);
      message = `${action === "pause" ? "Jeda" : "Lanjutkan"} rewards diantrekan untuk blockchain worker`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim perintah";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Blockchain — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Blockchain"
    title="Blockchain"
    subtitle="Status kontrak OryphemCoin dan kontrol hadiah on-chain."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  {#if loading}
    <div class="mt-6 skeleton h-40"></div>
  {:else if status}
    <div class="card mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <div class="mono-label">Jaringan</div>
        <div class="font-semibold">{status.network}</div>
      </div>
      <div>
        <div class="mono-label">ID Chain</div>
        <div class="font-semibold">{status.chain_id}</div>
      </div>
      <div>
        <div class="mono-label">Mode</div>
        <div class="font-semibold">{status.dry_run ? "uji coba" : "langsung"}</div>
      </div>
      <div>
        <div class="mono-label">Konfirmasi</div>
        <div class="font-semibold">{status.confirmations_required}</div>
      </div>
      <div class="sm:col-span-2">
        <div class="mono-label">Kontrak</div>
        <div class="break-all font-mono text-xs">
          {status.contract_address ?? "belum diterapkan"}
        </div>
      </div>
      <div class="sm:col-span-2">
        <div class="mono-label">Treasury</div>
        <div class="break-all font-mono text-xs">{status.treasury_address ?? "belum diatur"}</div>
      </div>
    </div>

    <div class="mt-4 flex gap-2">
      <button class="btn-ghost" on:click={() => control("pause")} disabled={busy === "pause"}>
        {busy === "pause" ? "Mengirim…" : "Jeda hadiah"}
      </button>
      <button class="btn-primary" on:click={() => control("unpause")} disabled={busy === "unpause"}>
        {busy === "unpause" ? "Mengirim…" : "Lanjutkan hadiah"}
      </button>
    </div>
  {/if}

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
