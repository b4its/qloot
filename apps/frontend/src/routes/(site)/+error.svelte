<script lang="ts">
  import { page } from "$app/stores";
  import Icon from "$lib/components/Icon.svelte";

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
  $: icon = status === 404 ? "compass" : status === 403 ? "lock" : "triangle-exclamation";
</script>

<svelte:head><title>{status} — QLoot</title></svelte:head>

<div class="relative grid min-h-[70vh] place-items-center overflow-hidden px-4">
  <div class="aurora"></div>
  <div class="relative z-10 max-w-md text-center">
    <span
      class="mx-auto grid h-16 w-16 place-items-center rounded-hero text-white"
      style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
    >
      <Icon name={icon} size="26px" />
    </span>
    <p class="mono-label mt-6">Error {status}</p>
    <h1 class="mt-1 font-display text-3xl font-bold">{message}</h1>
    <p class="mt-2 muted">{detail}</p>
    <div class="mt-6 flex flex-wrap justify-center gap-3">
      <a href="/" class="btn-primary"><Icon name="house" size="12px" /> Ke beranda</a>
      <a href="/courses" class="btn-secondary">Jelajahi kursus</a>
    </div>
  </div>
</div>
