<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
</script>

<svelte:head><title>Untuk Bisnis — QLoot</title></svelte:head>

<section class="relative overflow-hidden border-b">
  <div class="aurora"></div>
  <div class="relative z-10 mx-auto max-w-4xl px-4 py-16 sm:px-6">
    <p class="mono-label">Untuk Bisnis</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Tingkatkan skill tim Anda</h1>
    <p class="mt-3 muted">
      Program pelatihan terkurasi, laporan kemajuan, dan sertifikasi digital untuk kebutuhan
      organisasi.
    </p>
    <a href="/register" class="btn-primary mt-6"
      ><Icon name="briefcase" size="13px" /> Konsultasi Gratis</a
    >
  </div>
</section>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <div class="grid gap-6 sm:grid-cols-3">
    {#each [{ icon: "users-gear", t: "Onboarding Tim", d: "Jalur belajar khusus untuk peran teknis dan non-teknis." }, { icon: "chart-line", t: "Laporan Kemajuan", d: "Pantau progres, sertifikat, dan capaian tim secara berkala." }, { icon: "shield-halved", t: "Keamanan & Kepatuhan", d: "Data pelajar aman; learning data tidak dipublikasikan on-chain." }] as f}
      <div class="card lift">
        <span class="tile-cool h-11 w-11"><Icon name={f.icon} size="18px" /></span>
        <h2 class="mt-3 font-display text-lg font-bold">{f.t}</h2>
        <p class="mt-1 text-sm muted">{f.d}</p>
      </div>
    {/each}
  </div>
</div>
