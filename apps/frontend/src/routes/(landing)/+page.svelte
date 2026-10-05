<script lang="ts">
  import { reveal } from "$lib/actions/reveal";
  import Icon from "$lib/components/Icon.svelte";
  import StatCounter from "$lib/components/StatCounter.svelte";
  import CertificateBadge from "$lib/components/CertificateBadge.svelte";
  import CoinIcon from "$lib/components/CoinIcon.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";
  import BrandLogo from "$lib/components/BrandLogo.svelte";
  import Mascot from "$lib/components/Mascot.svelte";
  import { auth } from "$lib/stores/auth";
  import { classTracks, features, mentors, testimonials } from "$lib/data/content";

  $: user = $auth.user;

  function initials(name: string): string {
    return name
      .split(" ")
      .map((n) => n[0])
      .slice(0, 2)
      .join("");
  }
</script>

<svelte:head>
  <title>QLoot | E-Learning Kelas dengan AI & Reward On-Chain</title>
</svelte:head>

<!-- ================= HERO ================= -->
<section class="relative overflow-hidden">
  <div class="aurora"><span class="aurora-blob-3"></span></div>

  <div
    class="relative z-10 mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24"
  >
    <div class="flex flex-col justify-center">
      <span class="neon-chip w-fit"
        ><Icon name="graduation-cap" size="10px" /> Platform e-learning kelas</span
      >
      <h1
        class="chroma mt-5 font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl"
      >
        Belajar sesuai kelasmu,<br />
        didampingi <span class="text-grad">AI & guru</span>.
      </h1>
      <p class="mt-5 max-w-xl text-ink2">
        Guru membuat pelajaran dan menargetkannya ke kelas tertentu. Siswa langsung melihat
        pelajaran, materi, ujian, dan quest untuk kelasnya, lengkap dengan reward OryphemToken.
      </p>
      <div class="mt-7 flex flex-wrap items-center gap-3">
        {#if user}
          <a href="/learning" class="btn-primary"
            ><Icon name="book-open-reader" size="13px" /> Pelajaran Saya</a
          >
          <a href="/dashboard" class="btn-secondary">Buka Dashboard</a>
        {:else}
          <a href="/register" class="btn-primary"
            ><Icon name="rocket" size="13px" /> Daftar Sekarang</a
          >
          <a href="/courses" class="btn-secondary"
            ><Icon name="compass" size="13px" /> Lihat Pelajaran</a
          >
        {/if}
      </div>
      <div class="mt-6 flex flex-wrap items-center gap-4 text-xs muted">
        <span class="inline-flex items-center gap-1.5"
          ><Icon name="circle-check" class="text-secondary" size="12px" /> Pelajaran per kelas</span
        >
        <span class="inline-flex items-center gap-1.5"
          ><Icon name="circle-check" class="text-secondary" size="12px" /> Penilaian AI</span
        >
        <span class="inline-flex items-center gap-1.5"
          ><Icon name="circle-check" class="text-secondary" size="12px" /> Sertifikat digital</span
        >
      </div>
    </div>

    <!-- Hero visual: Mascot Qlo + Holographic Class Card -->
    <div class="relative flex items-center justify-center lg:justify-end">
      <!-- Ambient aura background -->
      <div
        class="absolute -inset-4 -z-10 rounded-full bg-gradient-to-tr from-primary/20 via-cyan-400/10 to-yellow-400/10 blur-3xl opacity-75"
        aria-hidden="true"
      ></div>

      <!-- Mascot Qlo full body -->
      <div class="relative z-10 flex flex-col items-center">
        <Mascot
          mode="pose"
          pose="front"
          size="hero"
          float
          glow
          interactive
          speech="Hai! Aku Qlo, asisten belajarmu di Night City!"
          speechPosition="top"
          alt="Mascot Qlo QLoot"
          class="drop-shadow-2xl"
        />

        <!-- Floating holographic identity badge -->
        <div
          class="card neon-corners !py-2 !px-4 mt-3 flex items-center gap-3 bg-surface/90 shadow-xl backdrop-blur-md"
        >
          <span class="grid h-8 w-8 place-items-center rounded bg-primary/20 text-primary">
            <Icon name="wand-magic-sparkles" size="14px" />
          </span>
          <div class="leading-tight text-left">
            <p class="text-xs font-bold text-ink">Qlo · Asisten & Maskot QLoot</p>
            <p class="text-[10px] muted">Misi Kelas · Panduan Karier · Hadiah On-Chain</p>
          </div>
        </div>
      </div>

      <!-- Floating class card overlapping smoothly on large displays -->
      <div class="absolute -left-12 top-6 hidden xl:block w-72 z-20">
        <div class="tilt">
          <div class="grad-border glow-cyan shadow-xl">
            <div class="card holo scan-sweep !p-4 bg-surface/90 backdrop-blur-md">
              <div class="flex items-center justify-between">
                <span class="badge badge-mint text-[10px]"
                  ><Icon name="chalkboard-user" size="9px" /> Kelas 1A · IPA</span
                >
                <span class="mono-label text-[10px]">AKTIF</span>
              </div>
              <h3 class="mt-2 font-display text-sm font-bold">Pelajaran Kelas 1A</h3>
              <p class="text-[11px] muted">Matematika & Fisika interaktif.</p>
              <div class="mt-3 flex items-center justify-between border-t pt-2">
                <span class="flex items-center gap-1 text-[11px] font-semibold text-highlight">
                  <CoinIcon size="14px" />
                  <span>+50 OPT Hadiah</span>
                </span>
                <a href="/courses" class="btn-primary !px-2.5 !py-1 text-[11px]">Buka</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- HUD telemetry strip -->
  <div
    class="relative z-10 mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 pb-8 sm:px-6"
  >
    <span class="data-rule flex-1">NIGHT_CITY // ONLINE</span>
    <span class="neon-chip blink">● LIVE</span>
  </div>
</section>

<!-- ================= LIVE STATS ================= -->
<section class="border-y bg-surface">
  <div class="mx-auto max-w-7xl px-4 py-10 sm:px-6">
    <div class="grid grid-cols-2 gap-6 lg:grid-cols-4">
      {#each [{ label: "Pelajar aktif", value: 12840, suffix: "+" }, { label: "Pelajaran", value: 96, suffix: "" }, { label: "Guru & pengajar", value: 42, suffix: "" }, { label: "Sertifikat diterbitkan", value: 5310, suffix: "+" }] as s}
        <div use:reveal>
          <p class="font-display text-3xl font-bold sm:text-4xl">
            <StatCounter value={s.value} suffix={s.suffix} />
          </p>
          <p class="mono-label mt-1">{s.label}</p>
        </div>
      {/each}
    </div>
    <p class="mt-4 text-center text-[11px] muted">
      Angka di atas bersifat ilustratif untuk demo dan bukan data langsung.
    </p>
  </div>
</section>

<!-- ================= FEATURES ================= -->
<section id="fitur" class="scroll-mt-20 mx-auto max-w-7xl px-4 py-16 sm:px-6">
  <div class="text-center" use:reveal>
    <span class="data-rule mx-auto max-w-xs">Kenapa QLoot</span>
    <h2 class="mt-3 font-display text-3xl font-bold sm:text-4xl">
      Satu ruang untuk kelas dan belajar
    </h2>
    <p class="mx-auto mt-2 max-w-2xl muted">
      Dirancang untuk sekolah: guru mengelola pelajaran per kelas, siswa fokus belajar.
    </p>
  </div>
  <div class="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
    {#each features as f, i}
      <div use:reveal={{ delay: i * 50 }} class="card holo lift">
        <span class="tile h-11 w-11">
          <Icon name={f.icon} size="18px" />
        </span>
        <h3 class="mt-3 font-display text-lg font-bold">{f.title}</h3>
        <p class="mt-1 text-sm muted">{f.desc}</p>
      </div>
    {/each}
  </div>
</section>

<!-- ================= CLASS TRACKS ================= -->
<section id="kelas" class="scroll-mt-20 border-t bg-surface">
  <div class="mx-auto max-w-7xl px-4 py-16 sm:px-6">
    <div class="flex flex-wrap items-end justify-between gap-4" use:reveal>
      <div>
        <p class="mono-label">Kelas</p>
        <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">
          Pelajaran mengikuti kelasmu
        </h2>
        <p class="mt-2 max-w-xl muted">
          Setiap kelas memiliki daftar pelajaran sendiri. Siswa hanya melihat kelas tempat mereka
          terdaftar.
        </p>
      </div>
    </div>
    <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {#each classTracks as t, i}
        <div use:reveal={{ delay: i * 60 }} class="grad-border lift h-full flex flex-col">
          <span class="holo flex h-full flex-col justify-between p-5">
            <div>
              <span
                class="brand-mark grid h-11 w-11 place-items-center rounded-sm glow-yellow"
                style={`background-image:${t.accent}`}
              >
                <Icon name={t.icon} size="18px" />
              </span>
              <span class="mt-4 block font-display text-lg font-bold">{t.label}</span>
              <span class="mt-2 flex flex-wrap gap-1.5">
                {#each t.subjects as s}<span class="btn-pill !py-0.5 !text-[11px]">{s}</span>{/each}
              </span>
            </div>
            <span class="mono-label mt-4 flex items-center gap-2">
              <Icon name="users" size="10px" />
              {t.students} siswa
            </span>
          </span>
        </div>
      {/each}
    </div>
  </div>
</section>

<!-- ================= MENTORS (TEACHERS) ================= -->
<section id="guru" class="scroll-mt-20 mx-auto max-w-7xl px-4 py-16 sm:px-6">
  <div use:reveal>
    <p class="mono-label">Guru & Pengajar</p>
    <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">Diajarkan oleh guru aktif</h2>
    <p class="mt-2 max-w-xl muted">
      Setiap pelajaran diampu oleh guru mata pelajaran yang berpengalaman.
    </p>
  </div>

  <div class="mt-8 flex snap-x gap-4 overflow-x-auto pb-2">
    {#each mentors as m, i}
      <div use:reveal={{ delay: i * 40 }} class="card w-72 flex-none snap-start">
        <div class="flex items-center gap-3">
          <span
            class="brand-mark-cool grid h-12 w-12 place-items-center rounded-sm font-display font-bold"
          >
            {initials(m.name)}
          </span>
          <div>
            <p class="font-semibold">{m.name}</p>
            <p class="text-xs muted">{m.role}</p>
          </div>
        </div>
        <p class="mt-3 text-sm muted">Mengampu mata pelajaran {m.subject}.</p>
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
<section id="sertifikat" class="scroll-mt-20 border-t bg-surface">
  <div class="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2">
    <div use:reveal class="flex flex-col justify-center">
      <p class="mono-label">Sertifikat Digital</p>
      <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">
        Kredensial yang bisa dibuktikan
      </h2>
      <p class="mt-3 muted">
        Setiap sertifikat memuat identitas unik dan tautan verifikasi. Bagikan ke portofolio atau
        simpan sebagai aset digital.
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
        title="Matematika 1A"
        subtitle="Siswa Kelas 1A"
        edition="#0142 / 5000"
        icon="square-root-variable"
      />
      <CertificateBadge
        title="Ekonomi 2D"
        subtitle="Siswa Kelas 2D"
        edition="#0087 / 5000"
        icon="chart-line"
      />
      <CertificateBadge
        title="Fisika 3A"
        subtitle="Siswa Kelas 3A"
        edition="#0311 / 2000"
        icon="atom"
      />
      <CertificateBadge
        title="Bahasa Indonesia"
        subtitle="Siswa Kelas 1A"
        edition="#0204 / 3000"
        icon="book"
      />
    </div>
  </div>
</section>

<!-- ================= TESTIMONIALS ================= -->
<section id="testimoni" class="scroll-mt-20 mx-auto max-w-7xl px-4 py-16 sm:px-6">
  <div use:reveal>
    <p class="mono-label">Testimoni</p>
    <h2 class="mt-2 font-display text-3xl font-bold sm:text-4xl">Kata guru dan siswa</h2>
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
  <div class="cyber-floor"></div>
  <div class="relative z-10 mx-auto max-w-3xl px-4 py-20 text-center sm:px-6">
    <span class="neon-chip">MULAI SEKARANG</span>
    <h2 class="chroma mt-4 font-display text-3xl font-bold sm:text-5xl">Siap memulai belajarmu?</h2>
    <p class="mt-4 muted">
      Daftar dengan kelasmu, dan langsung akses semua pelajaran yang disiapkan gurumu.
    </p>
    <div class="mt-8 flex flex-wrap justify-center gap-3">
      <a href="/register" class="btn-primary"><Icon name="rocket" size="13px" /> Daftar Sekarang</a>
      <a href="/courses" class="btn-secondary">Lihat Pelajaran</a>
    </div>
  </div>
</section>
