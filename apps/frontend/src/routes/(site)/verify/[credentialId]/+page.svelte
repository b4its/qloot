<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import { formatDate } from "$lib/utils/format";
  import type { CertificateVerify } from "$lib/types";

  let result: CertificateVerify | null = null;
  let loading = true;
  let error = "";
  let credentialId = "";

  onMount(async () => {
    credentialId = $page.params.credentialId ?? "";
    try {
      result = await api.get<CertificateVerify>(`/certificates/verify/${credentialId}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memverifikasi kredensial";
    } finally {
      loading = false;
    }
  });
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
        <p class="alert-error mt-5">{error}</p>
      {:else if result && result.valid}
        <p class="alert-ok mt-5"><Icon name="circle-check" size="12px" /> Kredensial valid</p>
        <div class="mt-4 grid gap-3 border-t pt-4 sm:grid-cols-2">
          <div>
            <p class="mono-label">Penerima</p>
            <p class="text-sm">{result.recipient_name}</p>
          </div>
          <div>
            <p class="mono-label">Pelajaran</p>
            <p class="text-sm">{result.course_title}</p>
          </div>
          <div>
            <p class="mono-label">Diterbitkan oleh</p>
            <p class="text-sm">{result.issued_by}</p>
          </div>
          <div>
            <p class="mono-label">Tanggal</p>
            <p class="text-sm">{result.issued_at ? formatDate(result.issued_at) : "—"}</p>
          </div>
          <div class="sm:col-span-2">
            <p class="mono-label">Hash verifikasi</p>
            <p class="mono break-all text-xs muted">{result.verification_hash}</p>
          </div>
          <div class="sm:col-span-2">
            <p class="mono-label">Status on-chain</p>
            {#if result.anchor_status === "anchored"}
              <p class="text-sm text-secondary">
                <Icon name="shield-halved" size="12px" /> Ter-anchor di jaringan (QTC)
                {#if result.anchor_tx_hash}
                  · <span class="mono break-all text-xs">{result.anchor_tx_hash}</span>
                {/if}
              </p>
            {:else if result.anchor_status === "anchoring" || result.anchor_status === "submitted"}
              <p class="text-sm muted">Menunggu konfirmasi jaringan…</p>
            {:else}
              <p class="text-sm muted">Belum di-anchor on-chain.</p>
            {/if}
          </div>
          <div class="sm:col-span-2 pt-2">
            <a
              class="btn-secondary inline-flex items-center gap-2 text-xs"
              href={`/api/v1/certificates/${credentialId}/render`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Icon name="file-lines" size="12px" /> Buka Dokumen Resmi (Cetak / PDF)
            </a>
          </div>
        </div>
      {:else}
        <p class="alert-error mt-5">
          <Icon name="circle-xmark" size="12px" /> Kredensial tidak ditemukan atau sudah dicabut.
        </p>
      {/if}

      <p class="mt-5 text-center text-sm muted">
        <a href="/certificates" class="text-primary hover:underline">Lihat sertifikat saya</a>
      </p>
    </div>
  </div>
</div>
