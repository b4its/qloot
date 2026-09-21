<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { api, ApiError } from "$lib/api/client";
  import { auth } from "$lib/stores/auth";

  interface Certificate {
    id: string;
    credential_id: string;
    verification_hash: string;
    course_id: string;
    course_title: string;
    recipient_name: string;
    issued_by: string;
    edition_number: number;
    edition_total: number;
    issued_at: string;
  }

  let certs: Certificate[] = [];
  let active: Certificate | null = null;
  let loading = true;
  let error = "";
  let copied = false;

  const verifyUrl = (id: string) =>
    typeof location !== "undefined"
      ? `${location.origin}/verify/${id}`
      : `/verify/${id}`;

  $: user = $auth.user;

  function pick(c: Certificate) {
    active = c;
    copied = false;
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
    const text = [
      "QLoot Academy — Sertifikat Kelulusan",
      "====================================",
      `Pelajaran : ${active.course_title}`,
      `Penerima  : ${active.recipient_name}`,
      `Diterbitkan oleh: ${active.issued_by}`,
      `Tanggal   : ${new Date(active.issued_at).toLocaleDateString("id-ID")}`,
      `ID Kredensial: ${active.credential_id}`,
      `Edisi     : #${String(active.edition_number).padStart(4, "0")} / ${active.edition_total}`,
      `Verifikasi: ${verifyUrl(active.credential_id)}`,
    ].join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${active.credential_id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
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
      certs = await api.get<Certificate[]>("/certificates");
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
          <a
            class="btn-ghost w-full"
            href="https://www.linkedin.com/profile/add?startTask=CERTIFICATION_NAME"
            target="_blank"
            rel="noopener"
          >
            <Icon name="linkedin" set="brands" size="12px" /> Tambah ke LinkedIn
          </a>
        </div>

        {#if certs.length > 1}
          <div class="card">
            <p class="mono-label mb-3">Sertifikat lain ({certs.length})</p>
            <ul class="space-y-2">
              {#each certs as c}
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
          </div>
        {/if}
      </aside>
    </div>
  {/if}
</div>
