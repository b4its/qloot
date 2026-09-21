<script lang="ts">
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let form = { title: "", duration_minutes: 60, passing_score_bp: 6000 };
  let busy = false;
  let error = "";
  let message = "";

  async function create() {
    error = "";
    message = "";
    busy = true;
    try {
      const exam = await api.post<Exam>("/exams", form);
      message = `Ujian "${exam.title}" dibuat.`;
      await goto(`/teacher/exams/${exam.id}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat ujian";
      busy = false;
    }
  }
</script>

<svelte:head><title>Ujian Baru — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Ujian"
    title="Ujian baru"
    subtitle="Tentukan judul, durasi, dan nilai kelulusan. Soal ditambahkan setelah ujian dibuat."
    backHref="/teacher/exams"
    backLabel="Ujian"
  />

  <PageAlerts {message} {error} />

  <div class="card mt-6">
    <div class="grid gap-3 sm:grid-cols-3">
      <label class="block sm:col-span-1">
        <span class="mono-label">Judul</span>
        <input class="input mt-1" placeholder="mis. Ulangan Bab 1" bind:value={form.title} />
      </label>
      <label class="block">
        <span class="mono-label">Durasi (menit)</span>
        <input class="input mt-1" type="number" min="1" bind:value={form.duration_minutes} />
      </label>
      <label class="block">
        <span class="mono-label">Passing score (bp)</span>
        <input
          class="input mt-1"
          type="number"
          min="0"
          max="10000"
          bind:value={form.passing_score_bp}
        />
      </label>
    </div>
    <p class="mt-2 text-xs muted">Passing score dalam basis points — 6000 = 60%.</p>
  </div>

  <div class="mt-4 flex items-center justify-end gap-2">
    <a href="/teacher/exams" class="btn-ghost">Batal</a>
    <button class="btn-primary" on:click={create} disabled={busy || form.title.trim().length < 2}>
      {#if busy}<Icon name="spinner" spin size="12px" />{:else}<Icon name="plus" size="12px" />{/if}
      Buat ujian
    </button>
  </div>
</div>
