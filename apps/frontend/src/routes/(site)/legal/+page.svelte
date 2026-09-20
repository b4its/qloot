<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";

  const sections = [
    {
      icon: "user-shield",
      t: "Privasi Data",
      d: "Kami hanya menyimpan data yang diperlukan untuk pengalaman belajar. Data pembelajaran dan data pribadi tidak dipublikasikan ke blockchain.",
    },
    {
      icon: "certificate",
      t: "Sertifikat Digital",
      d: "Sertifikat dapat diverifikasi melalui ID unik. Yang tercatat secara publik hanyalah metadata kredensial, bukan identitas pribadi.",
    },
    {
      icon: "cookie-bite",
      t: "Cookie",
      d: "Kami menggunakan cookie esensial untuk sesi login dan preferensi tema. Tidak ada pelacakan pihak ketiga untuk iklan.",
    },
    {
      icon: "scale-balanced",
      t: "Syarat Penggunaan",
      d: "Konten kursus dilindungi hak cipta. Penggunaan pribadi diperbolehkan; redistribusi komersial tidak.",
    },
  ];
</script>

<svelte:head><title>Legal & Privasi — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-16 sm:px-6">
  <p class="mono-label">Legal</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Legal & Privasi</h1>
  <p class="mt-2 muted">Komitmen kami terhadap transparansi dan keamanan data.</p>

  <div class="mt-8 space-y-4">
    {#each sections as s}
      <div class="card flex items-start gap-4">
        <span class="tile h-11 w-11"><Icon name={s.icon} size="17px" /></span>
        <div>
          <h2 class="font-display text-lg font-bold">{s.t}</h2>
          <p class="mt-1 text-sm muted">{s.d}</p>
        </div>
      </div>
    {/each}
  </div>
</div>
