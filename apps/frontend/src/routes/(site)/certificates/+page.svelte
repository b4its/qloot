<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import CertificateBadge from "$lib/components/CertificateBadge.svelte";
  import { auth } from "$lib/stores/auth";

  $: user = $auth.user;

  const sample = {
    title: "Desain Sistem untuk Web3",
    recipient: "Naya Ardhana",
    issuedBy: "QLoot Academy",
    date: "14 Juli 2026",
    id: "QLT-DSW3-0142-7F9A2C",
    edition: "#0142 / 5000",
  };
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
  <div class="grid gap-8 lg:grid-cols-[1fr_320px]">
    <!-- large badge -->
    <div class="grad-border">
      <div class="card !p-8">
        <div class="flex items-center justify-between">
          <span class="brand-mark grid h-14 w-14 place-items-center rounded-hero">
            <Icon name="certificate" size="24px" />
          </span>
          <span class="badge badge-mint"
            ><Icon name="shield-halved" size="11px" /> Terverifikasi</span
          >
        </div>
        <p class="mono-label mt-6">Sertifikat Kelulusan</p>
        <h2 class="mt-1 font-display text-3xl font-bold">{sample.title}</h2>
        <p class="mt-4 text-sm muted">Diberikan kepada</p>
        <p class="font-display text-xl font-bold">{user?.full_name ?? sample.recipient}</p>
        <div class="mt-6 grid gap-3 border-t pt-6 sm:grid-cols-2">
          <div>
            <p class="mono-label">Diterbitkan oleh</p>
            <p class="text-sm">{sample.issuedBy}</p>
          </div>
          <div>
            <p class="mono-label">Tanggal</p>
            <p class="text-sm">{sample.date}</p>
          </div>
          <div>
            <p class="mono-label">ID Kredensial</p>
            <p class="mono text-sm">{sample.id}</p>
          </div>
          <div>
            <p class="mono-label">Edisi</p>
            <p class="mono text-sm">{sample.edition}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- metadata + actions -->
    <aside class="space-y-4 h-fit lg:sticky lg:top-28">
      <div class="card">
        <p class="mono-label">Verifikasi</p>
        <div class="mt-3 flex items-center gap-2 rounded-sm border px-3 py-2">
          <Icon name="link" class="text-secondary" size="12px" />
          <span class="mono truncate text-xs">qloot.id/verify/{sample.id.toLowerCase()}</span>
        </div>
        <button
          class="btn-secondary mt-3 w-full"
          onclick={() => navigator.clipboard?.writeText(`qloot.id/verify/${sample.id}`)}
        >
          <Icon name="copy" size="12px" /> Salin tautan
        </button>
      </div>
      <div class="card space-y-2">
        <button class="btn-primary w-full"><Icon name="download" size="12px" /> Unduh PDF</button>
        <button class="btn-secondary w-full"><Icon name="share-nodes" size="12px" /> Bagikan</button
        >
        <button class="btn-ghost w-full"
          ><Icon name="linkedin" set="brands" size="12px" /> Tambah ke LinkedIn</button
        >
      </div>
      <div class="card">
        <p class="mono-label mb-3">Contoh lain</p>
        <CertificateBadge
          title="Fondasi AI"
          subtitle="Yoga Pratama"
          edition="#0087 / 5000"
          icon="microchip"
          compact
        />
      </div>
    </aside>
  </div>
</div>
