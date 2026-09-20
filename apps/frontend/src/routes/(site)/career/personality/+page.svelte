<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount } from "svelte";
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

  let answers: number[] = new Array(statements.length).fill(3);
  let result: Personality | null = null;
  let loading = true;
  let saving = false;
  let error = "";

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
    try {
      result = await api.get<Personality | null>("/career/personality");
    } catch {
      result = null;
    } finally {
      loading = false;
    }
  }

  async function submit() {
    saving = true;
    error = "";
    try {
      result = await api.post<Personality>("/career/personality", { answers });
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Could not score the test";
    } finally {
      saving = false;
    }
  }

  $: answered = answers.filter((a) => a > 0).length;

  onMount(load);
</script>

<svelte:head><title>Big Five Test — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Kepribadian</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Big Five Personality Test</h1>
      <p class="mt-1 text-sm muted">
        Kuesioner bergaya BFI-2 (simulasi) yang mengukur Keterbukaan, Kehati-hatian, Ekstroversi,
        Keramahan, dan Neurotisisme.
      </p>
    </div>
    <a href="/career" class="btn-ghost">← Career home</a>
  </div>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  <div class="mt-6 grid gap-4 lg:grid-cols-3">
    <div class="card lg:col-span-2">
      <h2 class="hud font-display text-lg font-bold">Questionnaire</h2>
      <div class="mt-2 flex items-center justify-between text-xs muted">
        <span>{answered} / {statements.length} answered</span>
        <span>skala 1 – 5</span>
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
                >
                  {li + 1}
                </button>
              {/each}
              <span class="ml-2 self-center text-[11px] muted">{labels[answers[i] - 1]}</span>
            </div>
          </div>
        {/each}
      </div>
      <button class="btn-primary mt-5 w-full" on:click={submit} disabled={saving}>
        {saving ? "Scoring…" : "Submit & see results"}
      </button>
    </div>

    <div class="card h-fit">
      <h2 class="hud font-display text-lg font-bold">Your result</h2>
      {#if loading}
        <p class="mt-2 muted">Loading…</p>
      {:else if result}
        <div class="mt-3 space-y-3">
          {#each traits as t}
            {@const value = result[t.key]}
            <div>
              <div class="flex items-center justify-between text-sm">
                <span class="inline-flex items-center gap-2"
                  ><Icon name={t.icon} size="12px" class="text-primary" /> {t.label}</span
                >
                <span class="font-mono">{value}</span>
              </div>
              <div class="track mt-1 h-1.5">
                <span style={`width:${value}%`}></span>
              </div>
            </div>
          {/each}
          {#if result.summary}
            <p class="alert-info mt-2">
              {result.summary}
            </p>
          {/if}
          <a href="/career/roadmap" class="btn-ghost w-full">See your career roadmap →</a>
        </div>
      {:else}
        <p class="mt-2 muted">
          No result yet. Complete the questionnaire to generate your profile.
        </p>
      {/if}
    </div>
  </div>
</div>
