<script lang="ts">
  import { page } from "$app/stores";
  import Icon from "$lib/components/Icon.svelte";
  import Mascot, { type MascotExpression } from "$lib/components/Mascot.svelte";

  $: status = $page.status;
  $: message =
    status === 404
      ? "Halaman tidak ditemukan"
      : status === 403
        ? "Akses ditolak"
        : "Terjadi kesalahan";
  $: detail =
    status === 404
      ? "Tautan mungkin sudah dipindahkan atau tidak pernah ada."
      : status === 403
        ? "Kamu tidak memiliki izin untuk membuka halaman ini."
        : ($page.error?.message ?? "Silakan coba lagi sebentar lagi.");
  $: mascotExpr = (
    status === 404 ? "confused" : status === 403 ? "surprised" : "sad"
  ) as MascotExpression;
  $: speech =
    status === 404
      ? "Waduh, jalannya buntu nih! Yuk balik ke beranda."
      : status === 403
        ? "Ups, area ini terkunci untuk akunmu."
        : "Ada sedikit gangguan teknis...";
</script>

<svelte:head><title>{status} | QLoot</title></svelte:head>

<div class="relative grid min-h-[70vh] place-items-center overflow-hidden px-4">
  <div class="aurora"></div>
  <div class="relative z-10 max-w-md text-center">
    <div class="mb-2">
      <Mascot
        expression={mascotExpr}
        size="xl"
        glow
        float
        interactive
        {speech}
        speechPosition="top"
        alt="Qlo"
      />
    </div>
    <p class="mono-label mt-6">Error {status}</p>
    <h1 class="mt-1 font-display text-3xl font-bold">{message}</h1>
    <p class="mt-2 muted">{detail}</p>
    <div class="mt-6 flex flex-wrap justify-center gap-3">
      <a href="/" class="btn-primary"><Icon name="house" size="12px" /> Ke beranda</a>
      <a href="/courses" class="btn-secondary">Jelajahi pelajaran</a>
    </div>
  </div>
</div>
