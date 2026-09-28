<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError, API_BASE } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import { formatDate } from "$lib/utils/format";
  import type { CertificateVerify } from "$lib/types";

  let result: CertificateVerify | null = null;
  let loading = true;
  let error = "";
  let credentialId = "";
  let copied = "";
  let copyError = "";
  // The client-side time this page performed the check (transparency).
  let checkedAt = "";

  async function copy(value: string, key: string) {
    if (!value) return;
    copyError = "";
    if (!navigator.clipboard?.writeText) {
      copyError = "Papan klip tidak tersedia. Salin manual dari teks di layar.";
      setTimeout(() => (copyError = ""), 4000);
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      copied = key;
      setTimeout(() => (copied = ""), 1500);
    } catch {
      copyError = "Tidak dapat menyalin otomatis. Salin manual dari teks di layar.";
      setTimeout(() => (copyError = ""), 4000);
    }
  }

  onMount(async () => {
    credentialId = $page.params.credentialId ?? "";
    try {
      result = await api.get<CertificateVerify>(`/certificates/verify/${credentialId}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memverifikasi kredensial";
    } finally {
      checkedAt = new Date().toLocaleString("id-ID");
      loading = false;
    }
  });

  // --- verification checklist -------------------------------------------------
  $: anchored = result?.anchor_status === "anchored";
  $: checks = result
    ? [
        { label: "Kredensial terdaftar & tidak dicabut", ok: result.valid },
        { label: "Hash verifikasi tersedia", ok: !!result.verification_hash },
        { label: "Sudah di-anchor on-chain (QTC)", ok: anchored },
      ]
    : [];
</script>

<svelte:head><title>Verifikasi Kredensial — QLoot</title></svelte:head>

<div class="relative grid min-h-[80vh] place-items-center overflow-hidden px-4 py-12">
  <div class="aurora"></div>
  <div class="relative z-10 w-full max-w-lg">
    <div class="card holo !p-7">
      <span class="brand-mark grid h-12 w-12 place-items-center rounded-sm">
        <Icon name="shield-halved" size="20px" />
      </span>
      <p class="mono-label mt-4">Verifikasi Kredensial</p>
      <h1 class="mt-1 font-display text-2xl font-bold">Pemeriksaan sertifikat</h1>
      <p class="mono mt-1 break-all text-xs muted">{credentialId}</p>

      {#if loading}
        <div class="skeleton mt-5 h-32"></div>
      {:else if error}
        <p class="alert-error mt-5" role="alert" aria-live="assertive">{error}</p>
      {:else if result && result.valid}
        <!-- Trust banner -->
        <div class="mt-5 flex items-center gap-3 rounded-sm border border-emerald-500/40 p-3">
          <span class="tile-neutral h-10 w-10">
            <Icon name="circle-check" size="18px" class="text-mint" />
          </span>
          <div>
            <p class="font-semibold text-mint">
              Kredensial valid {#if anchored}<span class="badge badge-mint ml-1">On-chain</span
                >{/if}
            </p>
            <p class="text-[11px] muted">Diverifikasi QLoot · {checkedAt}</p>
          </div>
        </div>

        <div class="mt-4 grid gap-3 border-t pt-4 sm:grid-cols-2">
          <div>
            <p class="mono-label">Penerima</p>
            <p class="text-sm">{result.recipient_name ?? "—"}</p>
          </div>
          <div>
            <p class="mono-label">Pelajaran</p>
            <p class="text-sm">{result.course_title ?? "—"}</p>
          </div>
          <div>
            <p class="mono-label">Diterbitkan oleh</p>
            <p class="text-sm">{result.issued_by ?? "—"}</p>
          </div>
          <div>
            <p class="mono-label">Tanggal</p>
            <p class="text-sm">{result.issued_at ? formatDate(result.issued_at) : "—"}</p>
          </div>
        </div>

        <!-- Verification checklist -->
        <div class="mt-4 border-t pt-4">
          <p class="mono-label">Hasil pemeriksaan</p>
          <ul class="mt-2 space-y-1 text-sm">
            {#each checks as c}
              <li class="flex items-center gap-2">
                <Icon
                  name={c.ok ? "circle-check" : "circle-xmark"}
                  size="12px"
                  class={c.ok ? "text-mint" : "text-tertiary"}
                />
                <span class:muted={!c.ok}>{c.label}</span>
              </li>
            {/each}
          </ul>
        </div>

        <!-- Hash + copy -->
        {#if result.verification_hash}
          <div class="mt-4 border-t pt-4">
            <div class="flex items-center justify-between">
              <p class="mono-label">Hash verifikasi</p>
              <button
                class="btn-ghost !py-0.5 text-[11px]"
                on:click={() => copy(result!.verification_hash!, "hash")}
              >
                <Icon name={copied === "hash" ? "check" : "copy"} size="10px" />
                {copied === "hash" ? "Tersalin" : "Salin"}
              </button>
            </div>
            <p class="mono mt-1 break-all text-xs muted">{result.verification_hash}</p>
          </div>
        {/if}

        <!-- On-chain status -->
        <div class="mt-4 border-t pt-4">
          <p class="mono-label">Status on-chain</p>
          {#if anchored}
            <p class="mt-1 text-sm text-secondary">
              <Icon name="shield-halved" size="12px" /> Ter-anchor di jaringan (QTC)
              {#if result.anchor_tx_hash}
                · <span class="mono break-all text-xs">{result.anchor_tx_hash}</span>
              {/if}
            </p>
          {:else if result.anchor_status === "anchoring" || result.anchor_status === "submitted"}
            <p class="mt-1 text-sm muted">Menunggu konfirmasi jaringan…</p>
          {:else}
            <p class="mt-1 text-sm muted">Belum di-anchor on-chain.</p>
          {/if}
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-2 border-t pt-4">
          <a
            class="btn-secondary inline-flex items-center gap-2 text-xs"
            href={`${API_BASE}/api/v1/certificates/${encodeURIComponent(credentialId)}/render`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Icon name="file-lines" size="12px" /> Buka Dokumen Resmi
          </a>
          <button class="btn-ghost text-xs" on:click={() => copy(location.href, "link")}>
            <Icon name={copied === "link" ? "check" : "link"} size="12px" />
            {copied === "link" ? "Tautan tersalin" : "Salin tautan verifikasi"}
          </button>
        </div>
        {#if copyError}
          <p class="mt-2 text-xs text-danger" role="alert" aria-live="assertive">{copyError}</p>
        {/if}
      {:else}
        <p class="alert-error mt-5" role="alert" aria-live="assertive">
          <Icon name="circle-xmark" size="12px" /> Kredensial tidak ditemukan atau sudah dicabut.
        </p>
      {/if}

      <p class="mt-5 text-center text-sm muted">
        <a href="/certificates" class="text-primary hover:underline">Lihat sertifikat saya</a>
      </p>
    </div>
  </div>
</div>
