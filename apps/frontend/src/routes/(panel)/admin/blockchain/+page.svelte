<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { BlockchainStatus } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import { formatNumber, statusLabel } from "$lib/utils/format";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  interface ContractDeployment {
    network: string;
    chain_id: number;
    name: string;
    address: string;
    treasury?: string | null;
    tx_hash?: string | null;
  }

  interface ContractData {
    assets: Record<string, { name: string; symbol: string; address?: string }>;
    treasury?: string | null;
    deployments: ContractDeployment[];
  }

  interface Allocation {
    id: string;
    reward_key: string;
    user_id: string;
    amount: number;
    status: string;
    quest_id?: string | null;
    tx_id?: string | null;
  }

  let status: BlockchainStatus | null = null;
  let contractData: ContractData | null = null;
  let allocations: Allocation[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";
  let pauseAsset = "OPT";
  // A pause/unpause is a critical on-chain control; require an explicit confirm.
  let confirming: { action: "pause" | "unpause"; asset: string } | null = null;

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
      const [st, cd, al] = await Promise.all([
        api.get<BlockchainStatus>("/blockchain/status/admin"),
        api.get<ContractData>("/blockchain/contract"),
        api.get<Allocation[]>("/blockchain/allocations?limit=10"),
      ]);
      status = st;
      contractData = cd;
      allocations = al;
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
    confirming = null;
    try {
      await api.post(`/admin/blockchain/${action}?asset=${pauseAsset}`);
      message = `${action === "pause" ? "Jeda" : "Lanjutkan"} ${pauseAsset} diantrekan untuk blockchain worker`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim perintah";
    } finally {
      busy = "";
    }
  }

  onMount(load);

  // --- allocation metrics ----------------------------------------------------
  $: confirmedAllocs = allocations.filter((a) => a.status === "confirmed").length;
  $: failedAllocs = allocations.filter((a) => a.status === "failed").length;
  $: pendingAllocs = allocations.length - confirmedAllocs - failedAllocs;
  $: totalAllocated = allocations.reduce((s, a) => s + a.amount, 0);

  // A paused asset is one whose worker submitted a pause; we surface the asset
  // count and per-asset address presence as the operational signals available.
  $: assetCount = status?.assets ? Object.keys(status.assets).length : 0;
  $: deployedContracts = contractData?.deployments?.length ?? 0;

  const allocTone: Record<string, string> = {
    confirmed: "badge-mint",
    failed: "badge-magenta",
    pending: "badge-amber",
    queued: "badge-amber",
    submitted: "badge-indigo",
  };
</script>

<svelte:head><title>Blockchain — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Blockchain"
    title="Blockchain"
    subtitle="Status 4 aset digital QLoot (OPT · QTC · ORT + ORX) dan kontrol on-chain."
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
      <div class="sm:col-span-4">
        <div class="mono-label">Treasury</div>
        <div class="break-all font-mono text-xs">{status.treasury_address ?? "belum diatur"}</div>
      </div>
    </div>

    {#if status.assets}
      <div class="mt-4 grid gap-3 sm:grid-cols-2">
        {#each Object.entries(status.assets) as [key, a]}
          <div class="card">
            <div class="flex items-center justify-between">
              <span class="badge badge-indigo">{key}</span>
              <span class="mono-label">{a.symbol}</span>
            </div>
            <h2 class="mt-2 font-display text-lg font-bold">{a.name}</h2>
            <p class="text-xs muted">{a.role}</p>
            <div class="mt-2 break-all font-mono text-xs">{a.address ?? "belum diterapkan"}</div>
          </div>
        {/each}
      </div>
    {/if}

    <div class="mt-4 flex flex-wrap items-center gap-2">
      <select class="input !w-auto" bind:value={pauseAsset} aria-label="Pilih aset">
        <option value="OPT">OPT</option>
        <option value="QTC">QTC</option>
        <option value="ORT">ORT</option>
      </select>
      <button
        class="btn-ghost"
        on:click={() => (confirming = { action: "pause", asset: pauseAsset })}
        disabled={!!busy}
      >
        <Icon name="pause" size="12px" /> Jeda aset
      </button>
      <button
        class="btn-primary"
        on:click={() => (confirming = { action: "unpause", asset: pauseAsset })}
        disabled={!!busy}
      >
        <Icon name="play" size="12px" /> Lanjutkan aset
      </button>
      <span class="mono-label ml-auto">
        {assetCount} aset · {deployedContracts} deployment
      </span>
    </div>
    {#if contractData && contractData.deployments && contractData.deployments.length > 0}
      <div class="card mt-6">
        <h2 class="font-display text-lg font-bold">Deployment Kontrak Aktif</h2>
        <p class="text-xs muted mb-3">Daftar deployment kontrak on-chain yang tercatat.</p>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead>
              <tr class="border-b text-muted">
                <th class="py-2">Nama</th>
                <th class="py-2">Jaringan (Chain ID)</th>
                <th class="py-2">Alamat Kontrak</th>
                <th class="py-2">Treasury</th>
                <th class="py-2">Tx Hash</th>
              </tr>
            </thead>
            <tbody>
              {#each contractData.deployments as d}
                <tr class="border-b last:border-0 font-mono">
                  <td class="py-2 font-semibold font-sans">{d.name}</td>
                  <td class="py-2">{d.network} ({d.chain_id})</td>
                  <td class="py-2 break-all">{d.address}</td>
                  <td class="py-2 break-all">{d.treasury ?? "—"}</td>
                  <td class="py-2 break-all">{d.tx_hash ?? "—"}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <div class="card mt-6">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h2 class="font-display text-lg font-bold">Alokasi Hadiah Terbaru</h2>
          <p class="text-xs muted">
            10 alokasi reward off-chain terbaru sebelum dimint ke blockchain.
          </p>
        </div>
      </div>
      {#if allocations.length === 0}
        <p class="text-xs muted italic">Belum ada alokasi hadiah yang tercatat.</p>
      {:else}
        <!-- Allocation metrics -->
        <div class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div class="card p-4">
            <p class="mono-label text-[10px]">Total OPT</p>
            <p class="mt-1 font-display text-2xl font-bold" data-role="allocated-total">
              {formatNumber(totalAllocated)}
            </p>
          </div>
          <div class="card p-4">
            <p class="mono-label text-[10px]">Terkonfirmasi</p>
            <p class="mt-1 font-display text-2xl font-bold text-mint">{confirmedAllocs}</p>
          </div>
          <div class="card p-4">
            <p class="mono-label text-[10px]">Tertunda</p>
            <p class="mt-1 font-display text-2xl font-bold text-highlight">{pendingAllocs}</p>
          </div>
          <div class="card p-4">
            <p class="mono-label text-[10px]">Gagal</p>
            <p class="mt-1 font-display text-2xl font-bold" class:text-danger={failedAllocs > 0}>
              {failedAllocs}
            </p>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead>
              <tr class="border-b text-muted">
                <th class="py-2">Reward Key</th>
                <th class="py-2">Jumlah</th>
                <th class="py-2">Status</th>
                <th class="py-2">User ID</th>
                <th class="py-2">Tx ID</th>
              </tr>
            </thead>
            <tbody>
              {#each allocations as a (a.id)}
                <tr class="border-b last:border-0 font-mono">
                  <td class="py-2 truncate max-w-[200px]" title={a.reward_key}>{a.reward_key}</td>
                  <td class="py-2 font-bold font-sans">{formatNumber(a.amount)} OPT</td>
                  <td class="py-2">
                    <span class="badge {allocTone[a.status] ?? 'badge-neutral'}">
                      {statusLabel(a.status)}
                    </span>
                  </td>
                  <td class="py-2">{a.user_id.slice(0, 8)}…</td>
                  <td class="py-2">{a.tx_id ? `${a.tx_id.slice(0, 8)}…` : "—"}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
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

<!-- Pause/unpause confirmation modal -->
{#if confirming}
  <ConfirmDialog
    title={confirming.action === "pause" ? "Jeda Aset On-Chain" : "Lanjutkan Aset On-Chain"}
    description={confirming.action === "pause"
      ? `Menjeda ${confirming.asset} akan mencegah semua transfer & reward aset ini hingga dilanjutkan. Perintah dikirim ke blockchain worker.`
      : `Melanjutkan ${confirming.asset} akan mengaktifkan kembali transfer & reward aset ini.`}
    hint="Tindakan ini tercatat di audit log."
    confirmLabel={confirming.action === "pause" ? "Ya, Jeda" : "Ya, Lanjutkan"}
    confirmRole="confirm-control"
    busy={busy !== ""}
    onConfirm={() => control(confirming!.action)}
    close={() => (confirming = null)}
  />
{/if}
