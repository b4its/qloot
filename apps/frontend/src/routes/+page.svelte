<script lang="ts">
  import { reveal } from "$lib/actions/reveal";
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import CertificateBadge from "$lib/components/CertificateBadge.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";
  import { auth } from "$lib/stores/auth";
  import { courses, learningPaths, mentors, testimonials, formatIDR } from "$lib/data/content";

  $: user = $auth.user;
  $: featured = courses.slice(0, 6);

  function initials(name: string): string {
    return name
      .split(" ")
      .map((n) => n[0])
      .slice(0, 2)
      .join("");
  }
</script>

<svelte:head>
  <title>QLoot — Belajar, Berkembang, dan Dapatkan Sertifikat Digital</title>
</svelte:head>

<!-- ================= HERO ================= -->
<section class="relative overflow-hidden">
  <div class="aurora"><span class="aurora-blob-3"></span></div>
  <div class="dotgrid absolute inset-0 z-0 opacity-60"></div>

  <div
    class="relative z-10 mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24"
  >
    <div class="flex flex-col justify-center">
      <span class="badge badge-indigo w-fit">
        <Icon name="bolt" size="10px" /> Platform belajar generasi baru
      </span>
      <h1
        class="mt-5 font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl"
      >
        Mulai perjalananmu,<br />
        kuasai <span class="text-grad">skill masa depan</span>.
      </h1>
      <p class="mt-5 max-w-xl text-ink2">
        Kursus terstruktur, jalur belajar terpandu, dan sertifikat digital yang dapat diverifikasi —
        diajarkan oleh praktisi aktif di bidang teknologi, desain, dan data.
      </p>
      <div class="mt-7 flex flex-wrap items-center gap-3">
        {#if user}
          <a href="/dashboard" class="btn-primary">
            <Icon name="gauge-high" size="13px" /> Buka Dashboard
          </a>
          <a href="/courses" class="btn-secondary">Lihat Katalog</a>
        {:else}
          <a href="/register" class="btn-primary">
            <Icon name="rocket" size="13px" /> Mulai Gratis
          </a>
          <a href="/courses" class="btn-secondary">
            <Icon name="compass" size="13px" /> Jelajahi Kursus
          </a>
        {/if}
      </div>
      <div class="mt-6 flex flex-wrap items-center gap-4 text-xs muted">
        <span class="inline-flex items-center gap-1.5"
          ><Icon name="circle-check" class="text-secondary" size="12px" /> Tanpa kartu kredit</span
        >
        <span class="inline-flex items-center gap-1.5"
          ><Icon name="circle-check" class="text-secondary" size="12px" /> Sertifikat digital</span
        >
        <span class="inline-flex items-center gap-1.5"
          ><Icon name="circle-check" class="text-secondary" size="12px" /> Akses selamanya</span
        >
      </div>
    </div>

    <!-- floating course card -->
    <div class="relative hidden lg:block">
      <div class="tilt">
        <div class="grad-border">
          <div class="card !p-5">
            <div class="flex items-center justify-between">
              <span class="badge badge-mint"><Icon name="star" size="10px" /> Kursus unggulan</span>
              <span class="mono-label">6 MINGGU</span>
            </div>
            <h3 class="mt-3 font-display text-xl font-bold">Desain Sistem untuk Web3</h3>
            <p class="text-sm muted">Bangun design system yang siap untuk produk on-chain.</p>
            <div
              class="mt-4 h-24 rounded-xl border"
              style="background-image:linear-gradient(135deg,rgba(91,72,255,.18),rgba(0,229,168,.18))"
            >
              <div class="grid h-full place-items-center">
                <Icon name="pen-ruler" size="30px" class="text-primary/70" />
              </div>
            </div>
            <div class="mt-4 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span
                  class="grid h-8 w-8 place-items-center rounded-full bg-ink/5 text-xs font-semibold"
                  >AP</span
                >
                <div class="leading-tight">
                  <p class="text-xs font-medium">Alya Prameswari</p>
                  <p class="text-[11px] muted">Lead Product Designer</p>
                </div>
              </div>
              <a href="/courses/design-system-web3" class="btn-primary !px-4 !py-2 text-xs">Lihat</a
              >
            </div>
          </div>
        </div>
      </div>

      <div class="absolute -bottom-6 -left-6 hidden xl:block">
        <div class="card !p-3">
          <WalletChip
            address="0x7a2f3b91c4d8e05f6a2b9c1b8e4d7f0a3c6b9d21"
            label="Pelajar"
            size={34}
          />
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ================= LIVE STATS ================= -->
<section class="border-y bg-surface">
  <div class="mx-auto grid max-w-7xl grid-cols-2 gap-6 px-4 py-10 sm:px-6 lg:grid-cols-4">
    {#each [{ label: "Pelajar aktif", value: 12840, suffix: "+" }, { label: "Kursus", value: 96, suffix: "" }, { label: "Mentor praktisi", value: 42, suffix: "" }, { label: "Sertifikat diterbitkan", value: 5310, suffix: "+" }] as s}
      <div use:reveal>
        <p class="font-display text-3xl font-bold sm:text-4xl">
          <StatCounter value={s.value} suffix={s.suffix} />
        </p>
        <p class="mono-label mt-1">{s.label}</p>
      </div>
    {/each}
  </div>
</section>

<!-- ================= LEARNING PATHS ================= -->
<section class="mx-auto max-w-7xl px-4 py-16 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4" use:reveal>
    <div>
      <p class="mono-label">Jalur Belajar</p>
      <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">Jalur belajar populer</h2>
      <p class="mt-2 max-w-xl muted">
        Rangkaian kursus terkurasi untuk membawamu dari nol hingga siap industri.
      </p>
    </div>
    <a href="/paths" class="btn-secondary">Semua jalur <Icon name="arrow-right" size="12px" /></a>
  </div>

  <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
    {#each learningPaths as p, i}
      <a href={`/paths/${p.slug}`} use:reveal={{ delay: i * 60 }} class="grad-border lift block">
        <span class="block p-5">
          <span
            class="grid h-11 w-11 place-items-center rounded-xl text-white"
            style={`background-image:${p.accent}`}
          >
            <Icon name={p.icon} size="18px" />
          </span>
          <span class="mt-4 block font-display text-lg font-bold">{p.title}</span>
          <span class="mt-1 block text-sm muted">{p.desc}</span>
          <span class="mono-label mt-4 flex items-center gap-3">
            <span>{p.courses} kursus</span><span>·</span><span>{p.weeks} minggu</span>
          </span>
        </span>
      </a>
    {/each}
  </div>
</section>

<!-- ================= FEATURED COURSES ================= -->
<section class="border-t bg-surface">
  <div class="mx-auto max-w-7xl px-4 py-16 sm:px-6">
    <div class="flex flex-wrap items-end justify-between gap-4" use:reveal>
      <div>
        <p class="mono-label">Kursus Unggulan</p>
        <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">Paling diminati minggu ini</h2>
      </div>
      <a href="/courses" class="btn-secondary"
        >Lihat semua <Icon name="arrow-right" size="12px" /></a
      >
    </div>

    <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {#each featured as c, i}
        <a
          href={`/courses/${c.slug}`}
          use:reveal={{ delay: i * 50 }}
          class="card lift block !p-0 overflow-hidden"
        >
          <span class="block h-32" style={`background-image:${c.accent}`}>
            <span class="grid h-full place-items-center">
              <Icon name={c.icon} size="34px" class="text-white/90" />
            </span>
          </span>
          <span class="block p-5">
            <span class="flex items-center justify-between">
              <span class="badge badge-neutral">{c.category}</span>
              <span class="inline-flex items-center gap-1 text-xs muted">
                <Icon name="star" class="text-highlight" size="11px" />
                {c.rating}
              </span>
            </span>
            <span class="mt-3 block font-display text-lg font-bold leading-snug">{c.title}</span>
            <span class="mt-1 block text-sm muted">{c.tagline}</span>
            <span class="mono-label mt-4 flex items-center gap-3">
              <span>{c.level}</span><span>·</span><span>{c.weeks} minggu</span><span>·</span><span
                >{c.hoursPerWeek} jam/minggu</span
              >
            </span>
            <span class="mt-4 flex items-center justify-between border-t pt-3">
              <span class="inline-flex items-center gap-2 text-xs muted">
                <Icon name="user-tie" size="12px" />
                {c.mentor}
              </span>
              <span class="font-display font-bold">{formatIDR(c.price)}</span>
            </span>
          </span>
        </a>
      {/each}
    </div>
  </div>
</section>

<!-- ================= MENTORS ================= -->
<section class="mx-auto max-w-7xl px-4 py-16 sm:px-6">
  <div use:reveal>
    <p class="mono-label">Mentor & Instruktur</p>
    <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">Diajarkan oleh praktisi aktif</h2>
    <p class="mt-2 max-w-xl muted">
      Belajar langsung dari orang yang membangun produk nyata setiap hari.
    </p>
  </div>

  <div class="mt-8 flex snap-x gap-4 overflow-x-auto pb-2">
    {#each mentors as m, i}
      <div use:reveal={{ delay: i * 40 }} class="card w-72 flex-none snap-start">
        <div class="flex items-center gap-3">
          <span
            class="grid h-12 w-12 place-items-center rounded-full font-display font-bold text-white"
            style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
          >
            {initials(m.name)}
          </span>
          <div>
            <p class="font-semibold">{m.name}</p>
            <p class="text-xs muted">{m.role}</p>
          </div>
        </div>
        <p class="mt-3 text-sm muted">{m.bio}</p>
        <div class="mt-3">
          <WalletChip
            address={`0x${m.handle.slice(2)}a1b2c3d4e5f60718293a4b5c6d7e8f90`}
            label={m.handle}
            size={26}
          />
        </div>
      </div>
    {/each}
  </div>
</section>

<!-- ================= CERTIFICATES ================= -->
<section class="border-t bg-surface">
  <div class="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2">
    <div use:reveal class="flex flex-col justify-center">
      <p class="mono-label">Sertifikat Digital</p>
      <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">
        Kredensial yang bisa dibuktikan
      </h2>
      <p class="mt-3 muted">
        Setiap sertifikat memuat identitas unik dan tautan verifikasi. Bagikan ke LinkedIn,
        portofolio, atau simpan sebagai aset digital.
      </p>
      <ul class="mt-6 space-y-3 text-sm">
        <li class="flex items-start gap-3">
          <Icon name="shield-halved" class="mt-0.5 text-primary" /> Verifikasi kredensial yang transparan
        </li>
        <li class="flex items-start gap-3">
          <Icon name="fingerprint" class="mt-0.5 text-primary" /> ID unik per penerbitan
        </li>
        <li class="flex items-start gap-3">
          <Icon name="share-nodes" class="mt-0.5 text-primary" /> Mudah dibagikan & diunduh
        </li>
      </ul>
      <div class="mt-6">
        <a href="/certificates" class="btn-secondary"
          >Lihat contoh sertifikat <Icon name="arrow-right" size="12px" /></a
        >
      </div>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <CertificateBadge
        title="Desain Sistem Web3"
        subtitle="Diberikan kepada Refa Anjani"
        edition="#0142 / 5000"
        icon="pen-ruler"
      />
      <CertificateBadge
        title="Fondasi AI"
        subtitle="Diberikan kepada Yoga Pratama"
        edition="#0087 / 5000"
        icon="microchip"
      />
      <CertificateBadge
        title="Smart Contract"
        subtitle="Diberikan kepada Sinta Maharani"
        edition="#0311 / 2000"
        icon="file-code"
      />
      <CertificateBadge
        title="Web Full-Stack"
        subtitle="Diberikan kepada Bima Aditya"
        edition="#0204 / 3000"
        icon="layer-group"
      />
    </div>
  </div>
</section>

<!-- ================= TESTIMONIALS ================= -->
<section class="mx-auto max-w-7xl px-4 py-16 sm:px-6">
  <div use:reveal>
    <p class="mono-label">Testimoni</p>
    <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">Kata mereka yang sudah mulai</h2>
  </div>
  <div class="mt-8 grid gap-5 lg:grid-cols-3">
    {#each testimonials as t, i}
      <figure use:reveal={{ delay: i * 60 }} class="card">
        <Icon name="quote-left" size="18px" class="text-primary/60" />
        <blockquote class="mt-3 text-sm leading-relaxed">{t.quote}</blockquote>
        <figcaption class="mt-4 border-t pt-3">
          <p class="text-sm font-semibold">{t.name}</p>
          <p class="text-xs muted">{t.role}</p>
        </figcaption>
      </figure>
    {/each}
  </div>
</section>

<!-- ================= FINAL CTA ================= -->
<section class="relative overflow-hidden border-t">
  <div class="aurora"><span class="aurora-blob-3"></span></div>
  <div class="relative z-10 mx-auto max-w-3xl px-4 py-20 text-center sm:px-6">
    <h2 class="font-display text-3xl font-bold sm:text-5xl">Siap memulai perjalananmu?</h2>
    <p class="mt-4 muted">
      Bergabung gratis, pilih jalur belajarmu, dan raih sertifikat digital pertamamu.
    </p>
    <div class="mt-8 flex flex-wrap justify-center gap-3">
      <a href="/register" class="btn-primary"><Icon name="rocket" size="13px" /> Daftar Sekarang</a>
      <a href="/paths" class="btn-secondary">Lihat Jalur Belajar</a>
    </div>
  </div>
</section>
