<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Personality } from "$lib/types";

  // A compact simulation of a BFI-2 style questionnaire.
  const statements = [
    "Saya suka mencari cara baru untuk menyelesaikan tugas.",
    "Saya menyelesaikan pekerjaan dengan teliti dan teratur.",
    "Saya mudah memulai percakapan dengan orang baru.",
    "Saya berusaha menjaga keharmonisan kelompok.",
    "Saya mudah merasa cemas saat menghadapi tekanan.",
    "Saya tertarik pada ide dan konsep yang abstrak.",
    "Saya membuat rencana sebelum bertindak.",
    "Saya merasa berenergi saat berada di keramaian.",
    "Saya suka membantu orang lain yang kesulitan.",
    "Saya sering mengkhawatirkan hal-hal kecil.",
    "Saya senang mencoba pengalaman baru.",
    "Saya menepati janji dan komitmen.",
    "Saya aktif dalam kegiatan kelompok.",
    "Saya menghargai pendapat orang lain.",
    "Saya tetap tenang dalam situasi sulit.",
  ];

  // 0 = unanswered so the progress bar reflects real completion.
  let answers: number[] = new Array(statements.length).fill(0);
  let result: Personality | null = null;
  let loading = true;
  let saving = false;
  let error = "";
  let message = "";
  // Distinguish "no profile yet" from "failed to load" so the panel does not
  // claim the user has never taken the test when the request simply failed.
  let loadError = "";
  // Retake keeps the stored profile on screen until a new questionnaire is
  // submitted, so leaving mid-way cannot silently wipe a saved result.
  let retaking = false;

  const labels = ["Sangat tidak setuju", "Tidak setuju", "Netral", "Setuju", "Sangat setuju"];

  const traits = [
    { key: "openness", label: "Keterbukaan", icon: "brain" },
    { key: "conscientiousness", label: "Kehati-hatian", icon: "puzzle-piece" },
    { key: "extraversion", label: "Ekstroversi", icon: "comments" },
    { key: "agreeableness", label: "Keramahan", icon: "handshake" },
    { key: "neuroticism", label: "Neurotisisme", icon: "water" },
  ] as const;

  async function load() {
    loading = true;
    loadError = "";
    try {
      result = await api.get<Personality | null>("/career/personality");
    } catch (e) {
      result = null;
      loadError = e instanceof ApiError ? e.message : "Gagal memuat profil kepribadian.";
    } finally {
      loading = false;
    }
  }

  async function submit() {
    if (!allAnswered || saving) return;
    saving = true;
    error = "";
    message = "";
    try {
      result = await api.post<Personality>("/career/personality", { answers });
      retaking = false;
      message = "Profil kepribadian diperbarui.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menilai tes";
    } finally {
      saving = false;
    }
  }

  function retake() {
    // Enter "retake mode" without discarding the saved profile: the previous
    // result stays visible (and stored server-side) until a new test is
    // submitted, so navigating away cannot lose it.
    retaking = true;
    answers = new Array(statements.length).fill(0);
    message = "";
    error = "";
  }

  function cancelRetake() {
    retaking = false;
    answers = new Array(statements.length).fill(0);
    error = "";
  }

  $: answered = answers.filter((a) => a > 0).length;
  $: completionPct = Math.round((answered / statements.length) * 100);
  $: allAnswered = answered === statements.length;

  // Rank the traits so the UI can surface the dominant one and a short profile.
  $: ranked = result
    ? [...traits].map((t) => ({ ...t, value: result![t.key] })).sort((a, b) => b.value - a.value)
    : [];
  $: dominant = ranked[0] ?? null;
  $: lowest = ranked.length ? ranked[ranked.length - 1] : null;

  onMount(load);
</script>

<svelte:head><title>Tes Big Five — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Kepribadian</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Tes Kepribadian Big Five</h1>
      <p class="mt-1 text-sm muted">
        Kuesioner bergaya BFI-2 (simulasi) yang mengukur Keterbukaan, Kehati-hatian, Ekstroversi,
        Keramahan, dan Neurotisisme.
      </p>
    </div>
    <a href="/career" class="btn-ghost">← Beranda karier</a>
  </div>

  {#if error}
    <p class="alert-error mt-4" role="alert" aria-live="assertive">
      {error}
    </p>
  {/if}
  {#if message}
    <p class="alert-ok mt-4" role="status" aria-live="polite">{message}</p>
  {/if}

  <div class="mt-6 grid gap-4 lg:grid-cols-3">
    <div class="card lg:col-span-2">
      <div class="flex items-center justify-between">
        <h2 class="hud font-display text-lg font-bold">Kuesioner</h2>
        <span class="mono-label">{answered} / {statements.length} · {completionPct}%</span>
      </div>

      <!-- Progress bar -->
      <div
        class="mt-2 h-2 w-full overflow-hidden rounded-full"
        style="background: rgb(var(--line))"
        role="progressbar"
        aria-valuenow={answered}
        aria-valuemin={0}
        aria-valuemax={statements.length}
        aria-label="Progres kuesioner"
      >
        <div
          class="h-full rounded-full transition-all {allAnswered ? 'bg-mint' : 'bg-primary'}"
          style={`width: ${completionPct}%`}
        ></div>
      </div>

      <div class="mt-1 flex items-center justify-between text-xs muted">
        <span>skala 1 – 5</span>
        {#if !allAnswered}
          <span>{statements.length - answered} pertanyaan tersisa</span>
        {:else}
          <span class="text-mint">Semua terjawab</span>
        {/if}
      </div>

      <div class="mt-3 space-y-4">
        {#each statements as s, i}
          <div>
            <p class="text-sm">{i + 1}. {s}</p>
            <div class="mt-1 flex flex-wrap gap-1">
              {#each labels as lbl, li}
                <button
                  type="button"
                  class="rounded-sm border px-2.5 py-1 font-mono text-[11px] transition"
                  class:border-primary={answers[i] === li + 1}
                  class:bg-primary={answers[i] === li + 1}
                  class:text-[#05060A]={answers[i] === li + 1}
                  class:hover:border-primary={answers[i] !== li + 1}
                  on:click={() => (answers[i] = li + 1)}
                  title={lbl}
                  aria-label={`Pertanyaan ${i + 1}: ${lbl}`}
                  aria-pressed={answers[i] === li + 1}
                >
                  {li + 1}
                </button>
              {/each}
              {#if answers[i] > 0}
                <span class="ml-2 self-center text-[11px] muted">{labels[answers[i] - 1]}</span>
              {:else}
                <span class="ml-2 self-center text-[11px] muted">Belum dijawab</span>
              {/if}
            </div>
          </div>
        {/each}
      </div>
      <button
        class="btn-primary mt-5 w-full"
        on:click={submit}
        disabled={saving || !allAnswered}
        data-role="submit"
      >
        {saving ? "Menilai …" : allAnswered ? "Kirim & lihat hasil" : "Jawab semua pertanyaan dulu"}
      </button>
    </div>

    <div class="card h-fit">
      <div class="flex items-center justify-between">
        <h2 class="hud font-display text-lg font-bold">Hasilmu</h2>
        {#if result && !loading}
          {#if retaking}
            <button class="btn-ghost !py-1 text-xs" on:click={cancelRetake}>
              <Icon name="xmark" size="11px" /> Batal ulangi
            </button>
          {:else}
            <button class="btn-ghost !py-1 text-xs" on:click={retake}>
              <Icon name="rotate" size="11px" /> Ulangi
            </button>
          {/if}
        {/if}
      </div>
      {#if retaking}
        <p class="alert-info mt-2 text-xs" role="status">
          <Icon name="circle-info" size="11px" class="inline-flex" /> Jawab ulang kuesioner di
          kiri lalu kirim untuk memperbarui hasil. Hasil saat ini tetap tersimpan sampai kamu
          mengirim yang baru.
        </p>
      {/if}
      {#if loading}
        <Skeleton rows={4} />
      {:else if loadError}
        <div class="mt-3 space-y-2" role="alert" aria-live="assertive">
          <p class="text-sm text-danger">{loadError}</p>
          <button class="btn-ghost !py-1 text-xs" on:click={load}>Coba lagi</button>
        </div>
      {:else if result}
        <div class="mt-3 space-y-3">
          {#if dominant}
            <div class="rounded-sm border p-3">
              <p class="mono-label text-[10px]">Ciri dominan</p>
              <p class="mt-1 flex items-center gap-2 font-semibold">
                <Icon name={dominant.icon} size="13px" class="text-primary" />
                {dominant.label}
                <span class="mono ml-auto text-sm">{dominant.value}</span>
              </p>
              {#if lowest && lowest.key !== dominant.key}
                <p class="mt-1 text-xs muted">
                  Terendah: {lowest.label} ({lowest.value})
                </p>
              {/if}
            </div>
          {/if}

          {#each ranked as t}
            <div>
              <div class="flex items-center justify-between text-sm">
                <span class="inline-flex items-center gap-2"
                  ><Icon name={t.icon} size="12px" class="text-primary" /> {t.label}</span
                >
                <span class="font-mono">{t.value}</span>
              </div>
              <div class="track mt-1 h-1.5">
                <span style={`width:${t.value}%`} class:!bg-mint={t.key === dominant?.key}></span>
              </div>
            </div>
          {/each}
          {#if result.summary}
            <p class="alert-info mt-2">
              {result.summary}
            </p>
          {/if}
          <a href="/career/roadmap" class="btn-ghost w-full">Lihat peta jalan karirmu →</a>
        </div>
      {:else}
        <p class="mt-2 muted">Belum ada hasil. Selesaikan kuesioner untuk membuat profilmu.</p>
      {/if}
    </div>
  </div>
</div>
