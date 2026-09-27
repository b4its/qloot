<script lang="ts">
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let form = { title: "", duration_minutes: 60, max_attempts: 1 };
  // The backend uses basis points; the teacher thinks in percent. Keep the
  // percent as the source of truth for the UI and convert on submit.
  let passingPercent = 60;
  let busy = false;
  let error = "";
  let message = "";

  const DURATION_PRESETS = [15, 30, 45, 60, 90, 120];

  // --- validation ------------------------------------------------------------
  $: titleValid = form.title.trim().length >= 2;
  $: durationValid = form.duration_minutes >= 1 && form.duration_minutes <= 600;
  $: passingValid = passingPercent >= 0 && passingPercent <= 100;
  $: attemptsValid = form.max_attempts >= 0 && form.max_attempts <= 100;
  $: passingBp = Math.round(passingPercent * 100);
  $: canSubmit = titleValid && durationValid && passingValid && attemptsValid && !busy;
  $: durationLabel =
    form.duration_minutes >= 60
      ? `${Math.floor(form.duration_minutes / 60)} jam ${form.duration_minutes % 60 ? `${form.duration_minutes % 60} mnt` : ""}`.trim()
      : `${form.duration_minutes} menit`;

  async function create() {
    error = "";
    message = "";
    if (!titleValid) {
      error = "Judul ujian minimal 2 karakter.";
      return;
    }
    if (!durationValid) {
      error = "Durasi harus antara 1 dan 600 menit.";
      return;
    }
    if (!passingValid) {
      error = "Nilai kelulusan harus antara 0% dan 100%.";
      return;
    }
    busy = true;
    try {
      const exam = await api.post<Exam>("/exams", {
        title: form.title.trim(),
        duration_minutes: form.duration_minutes,
        passing_score_bp: passingBp,
        max_attempts: form.max_attempts,
      });
      message = `Ujian "${exam.title}" dibuat.`;
      await goto(`/teacher/exams/${exam.id}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat ujian";
      busy = false;
    }
  }
</script>

<svelte:head><title>Ujian Baru — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Ujian"
    title="Ujian baru"
    subtitle="Tentukan judul, durasi, dan nilai kelulusan. Soal ditambahkan setelah ujian dibuat."
    backHref="/teacher/exams"
    backLabel="Ujian"
  />

  <PageAlerts {message} {error} />

  <div class="mt-6 grid gap-4 lg:grid-cols-[1fr_300px]">
    <form class="card" on:submit|preventDefault={create} aria-label="Form ujian baru">
      <p class="mono-label">Detail ujian</p>
      <div class="mt-2 space-y-4">
        <label class="block">
          <span class="mono-label">Judul</span>
          <input
            class="input mt-1"
            placeholder="mis. Ulangan Bab 1"
            bind:value={form.title}
            required
            aria-invalid={form.title.length > 0 && !titleValid}
          />
          {#if form.title.length > 0 && !titleValid}
            <span class="mt-1 block text-[11px] text-danger">Minimal 2 karakter.</span>
          {/if}
        </label>

        <div>
          <span class="mono-label">Durasi (menit)</span>
          <div class="mt-1 flex flex-wrap items-center gap-2">
            <input
              class="input w-28"
              type="number"
              min="1"
              max="600"
              bind:value={form.duration_minutes}
              aria-label="Durasi menit"
            />
            {#each DURATION_PRESETS as d}
              <button
                type="button"
                class="btn-pill !py-1 text-xs"
                class:!border-primary={form.duration_minutes === d}
                class:!text-primary={form.duration_minutes === d}
                on:click={() => (form.duration_minutes = d)}
              >
                {d} mnt
              </button>
            {/each}
          </div>
          {#if !durationValid && form.duration_minutes !== null}
            <span class="mt-1 block text-[11px] text-danger">Harus antara 1 dan 600 menit.</span>
          {/if}
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <label class="block">
            <span class="mono-label">Nilai kelulusan (%)</span>
            <input class="input mt-1" type="number" min="0" max="100" bind:value={passingPercent} />
            <span class="mt-1 block text-[11px] muted"
              >{passingPercent}% = {passingBp} basis points</span
            >
          </label>
          <label class="block">
            <span class="mono-label">Maks. percobaan (0 = tak terbatas)</span>
            <input
              class="input mt-1"
              type="number"
              min="0"
              max="100"
              bind:value={form.max_attempts}
            />
          </label>
        </div>
      </div>

      <div class="mt-5 flex items-center justify-end gap-2 border-t pt-4">
        <a href="/teacher/exams" class="btn-ghost">Batal</a>
        <button class="btn-primary" type="submit" disabled={!canSubmit}>
          {#if busy}<Icon name="spinner" spin size="12px" />{:else}<Icon
              name="plus"
              size="12px"
            />{/if}
          Buat ujian
        </button>
      </div>
    </form>

    <!-- Live preview -->
    <aside class="card h-fit lg:sticky lg:top-28">
      <p class="mono-label">Pratinjau</p>
      <div class="mt-3 flex items-center justify-between">
        <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
          <Icon name="file-pen" size="17px" />
        </span>
        <span class="badge badge-neutral">Draf</span>
      </div>
      <h2 class="mt-3 font-display text-lg font-bold">{form.title.trim() || "Judul ujian"}</h2>
      <div class="mono-label mt-2 flex flex-wrap items-center gap-3">
        <span><Icon name="clock" size="10px" /> {durationLabel}</span>
        <span>·</span>
        <span><Icon name="bullseye" size="10px" /> lulus {passingPercent}%</span>
      </div>
      <p class="mt-3 border-t pt-3 text-xs muted">
        <Icon name="circle-info" size="10px" />
        {form.max_attempts === 0
          ? "Percobaan tak terbatas."
          : `Maksimal ${form.max_attempts} percobaan per siswa.`}
      </p>
    </aside>
  </div>
</div>
