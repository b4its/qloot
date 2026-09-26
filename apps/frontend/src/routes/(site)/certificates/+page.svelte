<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { api, ApiError } from "$lib/api/client";
  import { auth } from "$lib/stores/auth";
  import type { Certificate } from "$lib/types";
  import Pagination from "$lib/components/Pagination.svelte";
  import { paginate } from "$lib/utils/format";

  const LIST_PAGE_SIZE = 8;
  let certs: Certificate[] = [];
  let active: Certificate | null = null;
  let loading = true;
  let error = "";
  let copied = false;
  let revoking = false;
  let anchoring = false;
  let syncing = false;
  let syncNotice = "";
  let listPage = 1;
  let listQuery = "";
  let listStatus: "all" | "active" | "anchored" | "revoked" = "all";

  // --- overview metrics ------------------------------------------------------
  $: anchoredCount = certs.filter((c) => c.anchor_status === "anchored").length;
  $: revokedCount = certs.filter((c) => c.revoked_at).length;
  $: activeCount = certs.length - revokedCount;

  // --- filtered certificate list ---------------------------------------------
  $: filteredCerts = certs.filter((c) => {
    if (listStatus === "active" && c.revoked_at) return false;
    if (listStatus === "revoked" && !c.revoked_at) return false;
    if (listStatus === "anchored" && c.anchor_status !== "anchored") return false;
    if (listQuery.trim()) {
      const q = listQuery.toLowerCase().trim();
      if (!c.course_title.toLowerCase().includes(q) && !c.credential_id.toLowerCase().includes(q)) {
        return false;
      }
    }
    return true;
  });

  $: listTotalPages = Math.max(1, Math.ceil(filteredCerts.length / LIST_PAGE_SIZE));
  $: if (listPage > listTotalPages) listPage = 1;
  $: pagedCerts = paginate(filteredCerts, listPage, LIST_PAGE_SIZE);

  const verifyUrl = (id: string) =>
    typeof location !== "undefined" ? `${location.origin}/verify/${id}` : `/verify/${id}`;

  $: user = $auth.user;

  function pick(c: Certificate) {
    active = c;
    copied = false;
  }

  /** Re-check all completed courses and issue any missing certificates. */
  async function syncCertificates() {
    if (syncing) return;
    syncing = true;
    error = "";
    syncNotice = "";
    try {
      const synced = await api.post<Certificate[]>("/certificates/sync");
      certs = await api.get<Certificate[]>("/certificates?limit=200");
      if (certs.length > 0 && !active) {
        active = certs[0];
      }
      syncNotice = `Sinkronisasi selesai: ${synced.length} sertifikat berhasil diperiksa/diterbitkan.`;
      setTimeout(() => (syncNotice = ""), 4000);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menyinkronkan sertifikat";
    } finally {
      syncing = false;
    }
  }

  /** Admin-only: revoke the active credential (idempotent server-side). */
  async function revokeActive() {
    if (!active || revoking) return;
    const reason = window.prompt("Alasan pencabutan (opsional):") ?? "";
    revoking = true;
    error = "";
    try {
      const updated = await api.post<Certificate>(`/certificates/${active.credential_id}/revoke`, {
        reason: reason.trim() || null,
      });
      active = updated;
      certs = certs.map((c) => (c.id === updated.id ? updated : c));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mencabut sertifikat";
    } finally {
      revoking = false;
    }
  }

  /** Anchor the active certificate on-chain (costs 1 QTC). */
  async function anchorActive() {
    if (!active || anchoring) return;
    anchoring = true;
    error = "";
    try {
      const updated = await api.post<Certificate>(`/certificates/${active.credential_id}/anchor`);
      active = updated;
      certs = certs.map((c) => (c.id === updated.id ? updated : c));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal meng-anchor sertifikat";
    } finally {
      anchoring = false;
    }
  }

  async function copyLink() {
    if (!active) return;
    try {
      await navigator.clipboard?.writeText(verifyUrl(active.credential_id));
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  function download() {
    if (!active) return;
    // A self-contained, printable HTML certificate (open it and use the
    // browser's "Save as PDF"). Lighter than bundling a PDF library and it
    // renders the real credential, not a plain-text dump.
    const issued = new Date(active.issued_at).toLocaleDateString("id-ID", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
    const escape = (s: string) =>
      s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
    const edition = `#${String(active.edition_number).padStart(4, "0")} / ${active.edition_total}`;
    const html = `<!doctype html>
<html lang="id"><head><meta charset="utf-8" />
<title>Sertifikat ${escape(active.course_title)} — QLoot</title>
<style>
  @page { size: A4 landscape; margin: 0; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: Georgia, 'Times New Roman', serif; color: #1a1a2e;
    background: #f4f4f8; display: grid; place-items: center; min-height: 100vh; }
  .sheet { width: 297mm; height: 210mm; padding: 22mm; background: #fff;
    border: 6px solid #1a1a2e; position: relative; }
  .frame { border: 2px solid #b8a23a; height: 100%; padding: 14mm; text-align: center;
    display: flex; flex-direction: column; justify-content: center; }
  .brand { font-family: ui-monospace, monospace; letter-spacing: .35em; font-size: 13px;
    text-transform: uppercase; color: #b8a23a; }
  h1 { font-size: 40px; margin: 12mm 0 4mm; font-weight: 700; }
  .who { font-size: 26px; font-style: italic; margin: 4mm 0; }
  .line { width: 55%; margin: 6mm auto; border-top: 1px solid #ccc; }
  .meta { font-size: 13px; color: #555; line-height: 1.9; font-family: ui-monospace, monospace; }
  .seal { margin-top: 8mm; font-size: 12px; color: #888; }
</style></head>
<body><div class="sheet"><div class="frame">
  <div class="brand">QLoot Academy</div>
  <h1>Sertifikat Kelulusan</h1>
  <p>Diberikan kepada</p>
  <div class="who">${escape(active.recipient_name)}</div>
  <p>atas penyelesaian pelajaran</p>
  <h2 style="font-size:22px;margin:3mm 0">${escape(active.course_title)}</h2>
  <div class="line"></div>
  <div class="meta">
    Diterbitkan oleh: ${escape(active.issued_by)}<br />
    Tanggal: ${issued}<br />
    ID Kredensial: ${escape(active.credential_id)} · Edisi ${edition}
  </div>
  <div class="seal">Verifikasi: ${escape(verifyUrl(active.credential_id))}</div>
</div></div></body></html>`;
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sertifikat-${active.credential_id}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /** LinkedIn "add certification" flow, pre-filled with this credential. */
  function linkedinUrl(): string {
    if (!active) return "https://www.linkedin.com/profile/add?startTask=CERTIFICATION_NAME";
    const issued = new Date(active.issued_at);
    const p = new URLSearchParams({
      startTask: "CERTIFICATION_NAME",
      name: active.course_title,
      organizationName: "QLoot Academy",
      issueYear: String(issued.getFullYear()),
      issueMonth: String(issued.getMonth() + 1),
      certUrl: verifyUrl(active.credential_id),
      certId: active.credential_id,
    });
    return `https://www.linkedin.com/profile/add?${p.toString()}`;
  }

  async function share() {
    if (!active) return;
    const shareUrl = verifyUrl(active.credential_id);
    try {
      if (navigator.share) {
        await navigator.share({
          title: active.course_title,
          text: "Sertifikat QLoot",
          url: shareUrl,
        });
      } else {
        await navigator.clipboard?.writeText(shareUrl);
        copied = true;
        setTimeout(() => (copied = false), 1500);
      }
    } catch {
      /* user cancelled */
    }
  }

  onMount(async () => {
    try {
      certs = await api.get<Certificate[]>("/certificates?limit=200");
      active = certs[0] ?? null;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat sertifikat";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>Sertifikat Digital — QLoot</title></svelte:head>

<section class="relative overflow-hidden border-b">
  <div class="aurora"></div>
  <div class="relative z-10 mx-auto max-w-5xl px-4 py-14 sm:px-6">
    <p class="mono-label">Kredensial Digital</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Sertifikat yang bisa dibuktikan</h1>
    <p class="mt-2 max-w-2xl muted">
      Setiap sertifikat memiliki ID unik dan tautan verifikasi. Bagikan ke LinkedIn, portofolio,
      atau simpan sebagai aset digital.
    </p>
    <div class="mt-4 flex flex-wrap items-center gap-3">
      <button class="btn-ghost text-xs" on:click={syncCertificates} disabled={syncing}>
        <Icon name="rotate" size="12px" />
        {syncing ? "Menyinkronkan…" : "Sinkronkan Sertifikat"}
      </button>
      {#if syncNotice}
        <span class="text-xs text-mint font-medium">{syncNotice}</span>
      {/if}
    </div>
  </div>
</section>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  {#if error}
    <p class="alert-error">{error}</p>
  {:else if loading}
    <div class="grid gap-8 lg:grid-cols-[1fr_320px]">
      <div class="skeleton h-72"></div>
      <div class="skeleton h-72"></div>
    </div>
  {:else if !active}
    <div class="card grid place-items-center py-16 text-center">
      <Icon name="certificate" size="28px" class="muted" />
      <p class="mt-3 font-display text-lg font-bold">Belum ada sertifikat</p>
      <p class="mt-1 text-sm muted">
        Selesaikan seluruh materi pada sebuah pelajaran untuk mendapatkan sertifikat digital.
      </p>
      <a href="/learning" class="btn-primary mt-5"
        ><Icon name="book-open-reader" size="12px" /> Lihat Pelajaran Saya</a
      >
    </div>
  {:else}
    <!-- Overview metrics -->
    {#if certs.length > 0}
      <div class="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="card p-4">
          <p class="mono-label text-[10px]">Total</p>
          <p class="mt-1 font-display text-3xl font-bold">{certs.length}</p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Aktif</p>
          <p class="mt-1 font-display text-3xl font-bold text-mint" data-role="active-count">
            {activeCount}
          </p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">On-chain</p>
          <p class="mt-1 font-display text-3xl font-bold text-secondary">{anchoredCount}</p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Dicabut</p>
          <p class="mt-1 font-display text-3xl font-bold">{revokedCount}</p>
        </div>
      </div>
    {/if}
    <div class="grid gap-8 lg:grid-cols-[1fr_320px]">
      <!-- large badge -->
      <div class="grad-border">
        <div class="card holo !p-8">
          <div class="flex items-center justify-between">
            <span class="brand-mark grid h-14 w-14 place-items-center rounded-hero glow-yellow">
              <Icon name="certificate" size="24px" />
            </span>
            <span class="badge badge-mint"
              ><Icon name="shield-halved" size="11px" /> Terverifikasi</span
            >
          </div>
          <p class="mono-label mt-6">Sertifikat Kelulusan</p>
          <h2 class="mt-1 font-display text-3xl font-bold">{active.course_title}</h2>
          <p class="mt-4 text-sm muted">Diberikan kepada</p>
          <p class="font-display text-xl font-bold">{active.recipient_name ?? user?.full_name}</p>
          <div class="mt-6 grid gap-3 border-t pt-6 sm:grid-cols-2">
            <div>
              <p class="mono-label">Diterbitkan oleh</p>
              <p class="text-sm">{active.issued_by}</p>
            </div>
            <div>
              <p class="mono-label">Tanggal</p>
              <p class="text-sm">{new Date(active.issued_at).toLocaleDateString("id-ID")}</p>
            </div>
            <div>
              <p class="mono-label">ID Kredensial</p>
              <p class="mono text-sm">{active.credential_id}</p>
            </div>
            <div>
              <p class="mono-label">Edisi</p>
              <p class="mono text-sm">
                #{String(active.edition_number).padStart(4, "0")} / {active.edition_total}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- metadata + actions -->
      <aside class="space-y-4 h-fit lg:sticky lg:top-28">
        <div class="card">
          <p class="mono-label">Verifikasi</p>
          <a
            class="mt-3 flex items-center gap-2 rounded-sm border px-3 py-2 transition-colors hover:border-primary"
            href={verifyUrl(active.credential_id)}
            target="_blank"
            rel="noopener"
          >
            <Icon name="link" class="text-secondary" size="12px" />
            <span class="mono truncate text-xs">{verifyUrl(active.credential_id)}</span>
          </a>
          <button class="btn-secondary mt-3 w-full" on:click={copyLink}>
            <Icon name={copied ? "check" : "copy"} size="12px" />
            {copied ? "Tersalin" : "Salin tautan"}
          </button>
        </div>
        <div class="card space-y-2">
          <button class="btn-primary w-full" on:click={download}>
            <Icon name="download" size="12px" /> Unduh
          </button>
          <a
            class="btn-secondary w-full"
            href={`/api/v1/certificates/${active.credential_id}/render`}
            target="_blank"
            rel="noopener"
          >
            <Icon name="print" size="12px" /> Cetak dokumen resmi
          </a>
          <button class="btn-secondary w-full" on:click={share}>
            <Icon name="share-nodes" size="12px" /> Bagikan
          </button>
          <a class="btn-ghost w-full" href={linkedinUrl()} target="_blank" rel="noopener">
            <Icon name="linkedin" set="brands" size="12px" /> Tambah ke LinkedIn
          </a>
          {#if !active.revoked_at}
            {#if active.anchor_status === "anchored"}
              <p class="text-xs text-secondary">
                <Icon name="shield-halved" size="11px" /> Ter-anchor on-chain (QTC)
                {#if active.anchor_tx_hash}
                  · <span class="mono-label">{active.anchor_tx_hash.slice(0, 12)}…</span>
                {/if}
              </p>
            {:else if active.anchor_status === "anchoring" || active.anchor_status === "submitted"}
              <p class="text-xs muted">
                <Icon name="spinner" spin size="11px" /> Menunggu konfirmasi chain…
              </p>
            {:else if active.anchor_status === "failed"}
              <p class="text-xs text-tertiary">Anchor gagal — QTC dikembalikan. Coba lagi.</p>
            {:else}
              <button class="btn-secondary w-full" on:click={anchorActive} disabled={anchoring}>
                <Icon name="link" size="12px" />
                {anchoring ? "Meng-anchor…" : "Anchor ke chain (1 QTC)"}
              </button>
            {/if}
          {/if}
          {#if user?.roles?.includes("admin") && !active.revoked_at}
            <button
              class="btn-ghost w-full !text-tertiary hover:!border-tertiary"
              on:click={revokeActive}
              disabled={revoking}
            >
              <Icon name="ban" size="12px" />
              {revoking ? "Mencabut…" : "Cabut sertifikat"}
            </button>
          {/if}
          {#if active.revoked_at}
            <p class="text-xs text-tertiary">
              Dicabut{active.revoked_reason ? `: ${active.revoked_reason}` : "."}
            </p>
          {/if}
        </div>

        {#if certs.length > 1}
          <div class="card">
            <div class="flex items-center justify-between">
              <p class="mono-label">Sertifikat lain ({certs.length})</p>
              {#if anchoredCount > 0}
                <span class="badge badge-indigo"
                  ><Icon name="shield-halved" size="9px" /> {anchoredCount} on-chain</span
                >
              {/if}
            </div>

            <!-- List search + status filter -->
            <div class="mt-3 space-y-2">
              <div class="relative">
                <Icon
                  name="magnifying-glass"
                  size="11px"
                  class="absolute left-2.5 top-1/2 -translate-y-1/2 muted"
                />
                <input
                  class="input text-xs !py-1.5 !pl-8 w-full"
                  placeholder="Cari sertifikat..."
                  bind:value={listQuery}
                  on:input={() => (listPage = 1)}
                  aria-label="Cari sertifikat"
                />
              </div>
              <div class="flex flex-wrap gap-1">
                {#each [["all", "Semua"], ["active", "Aktif"], ["anchored", "On-chain"], ["revoked", "Dicabut"]] as [val, label]}
                  <button
                    type="button"
                    class="badge"
                    class:badge-mint={listStatus === val}
                    class:badge-neutral={listStatus !== val}
                    on:click={() => {
                      listStatus = val as typeof listStatus;
                      listPage = 1;
                    }}
                  >
                    {label}
                  </button>
                {/each}
              </div>
            </div>

            {#if filteredCerts.length === 0}
              <p class="mt-4 text-center text-xs muted">Tidak ada sertifikat yang cocok.</p>
            {:else}
              <ul class="mt-2 space-y-2">
                {#each pagedCerts as c (c.id)}
                  <li>
                    <button
                      class="flex w-full items-center justify-between gap-2 rounded-sm border px-3 py-2 text-left text-sm transition-colors"
                      class:border-primary={c.id === active?.id}
                      on:click={() => pick(c)}
                    >
                      <span class="min-w-0 flex-1">
                        <span class="block truncate">{c.course_title}</span>
                        <span class="flex items-center gap-1.5">
                          {#if c.revoked_at}
                            <span class="text-[10px] text-tertiary">Dicabut</span>
                          {:else if c.anchor_status === "anchored"}
                            <span class="text-[10px] text-secondary">On-chain</span>
                          {:else}
                            <span class="text-[10px] muted">Aktif</span>
                          {/if}
                          <span class="text-[10px] muted"
                            >· #{String(c.edition_number).padStart(4, "0")}</span
                          >
                        </span>
                      </span>
                      <Icon name="chevron-right" size="10px" class="flex-none muted" />
                    </button>
                  </li>
                {/each}
              </ul>
              <Pagination
                page={listPage}
                pageSize={LIST_PAGE_SIZE}
                total={filteredCerts.length}
                label="sertifikat"
                onPrev={() => (listPage = Math.max(1, listPage - 1))}
                onNext={() => (listPage = Math.min(listTotalPages, listPage + 1))}
              />
            {/if}
          </div>
        {/if}
      </aside>
    </div>
  {/if}
</div>
