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
  let listPage = 1;
  $: listTotalPages = Math.max(1, Math.ceil(certs.length / LIST_PAGE_SIZE));
  $: if (listPage > listTotalPages) listPage = 1;
  $: pagedCerts = paginate(certs, listPage, LIST_PAGE_SIZE);

  const verifyUrl = (id: string) =>
    typeof location !== "undefined" ? `${location.origin}/verify/${id}` : `/verify/${id}`;

  $: user = $auth.user;

  function pick(c: Certificate) {
    active = c;
    copied = false;
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
      const updated = await api.post<Certificate>(
        `/certificates/${active.credential_id}/anchor`,
      );
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
              <p class="text-xs muted"><Icon name="spinner" spin size="11px" /> Menunggu konfirmasi chain…</p>
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
            <p class="mono-label mb-3">Sertifikat lain ({certs.length})</p>
            <ul class="space-y-2">
              {#each pagedCerts as c}
                <li>
                  <button
                    class="flex w-full items-center justify-between gap-2 rounded-sm border px-3 py-2 text-left text-sm transition-colors"
                    class:border-primary={c.id === active?.id}
                    on:click={() => pick(c)}
                  >
                    <span class="truncate">{c.course_title}</span>
                    <Icon name="chevron-right" size="10px" class="flex-none muted" />
                  </button>
                </li>
              {/each}
            </ul>
            <Pagination
              page={listPage}
              pageSize={LIST_PAGE_SIZE}
              total={certs.length}
              label="sertifikat"
              onPrev={() => (listPage = Math.max(1, listPage - 1))}
              onNext={() => (listPage = Math.min(listTotalPages, listPage + 1))}
            />
          </div>
        {/if}
      </aside>
    </div>
  {/if}
</div>
