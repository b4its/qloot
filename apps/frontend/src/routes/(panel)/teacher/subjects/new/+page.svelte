<script lang="ts">
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const classTypes = ["IPA", "IPS", "Bahasa", "Umum"];

  // Canonical subject names offered as suggestions (still free-text).
  const SUBJECT_SUGGESTIONS = [
    "Matematika",
    "Fisika",
    "Kimia",
    "Biologi",
    "B. Indonesia",
    "B. Inggris",
    "Ekonomi",
    "Sejarah",
    "Sosiologi",
    "Geografi",
  ];

  let form = {
    title: "",
    subject: "",
    class_code: "1A",
    class_type: "IPA",
    description: "",
  };
  let busy = false;
  let error = "";
  let message = "";

  // --- inline validation + live preview --------------------------------------
  $: titleValid = form.title.trim().length >= 2;
  $: classValid = form.class_code.trim().length >= 1;
  $: canSubmit = titleValid && classValid && !busy;
  $: classLabel = `${form.class_code.trim() || "—"}${form.class_type ? ` · ${form.class_type}` : ""}`;

  async function create() {
    error = "";
    message = "";
    if (!titleValid) {
      error = "Judul pelajaran minimal 2 karakter.";
      return;
    }
    if (!classValid) {
      error = "Kelas wajib diisi (mis. 1A).";
      return;
    }
    busy = true;
    try {
      const payload = {
        title: form.title.trim(),
        subject: form.subject.trim() || null,
        class_code: form.class_code.trim(),
        class_type: form.class_type || null,
        description: form.description.trim() || null,
      };
      const course = await api.post<Course>("/courses", payload);
      message = "Pelajaran dibuat.";
      await goto(`/teacher/subjects/${course.id}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat pelajaran";
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head><title>Pelajaran Baru — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Pelajaran"
    title="Pelajaran baru"
    subtitle="Tentukan kelas dan tipe kelasnya. Siswa di kelas tersebut otomatis dapat mengakses."
    backHref="/teacher/subjects"
    backLabel="Pelajaran"
  />

  <PageAlerts {message} {error} />

  <div class="mt-6 grid gap-4 lg:grid-cols-[1fr_300px]">
    <form class="card" on:submit|preventDefault={create} aria-label="Form pelajaran baru">
      <p class="mono-label">Detail pelajaran</p>
      <div class="mt-2 grid gap-4 sm:grid-cols-2">
        <label class="block sm:col-span-2">
          <span class="mono-label">Nama pelajaran</span>
          <input
            class="input mt-1"
            placeholder="mis. Matematika 1A"
            bind:value={form.title}
            required
            aria-invalid={form.title.length > 0 && !titleValid}
          />
          {#if form.title.length > 0 && !titleValid}
            <span class="mt-1 block text-[11px] text-danger">Minimal 2 karakter.</span>
          {/if}
        </label>
        <label class="block">
          <span class="mono-label">Mata pelajaran</span>
          <input
            class="input mt-1"
            placeholder="mis. Matematika"
            list="subject-suggestions"
            bind:value={form.subject}
          />
          <datalist id="subject-suggestions">
            {#each SUBJECT_SUGGESTIONS as s}<option value={s}></option>{/each}
          </datalist>
        </label>
        <label class="block">
          <span class="mono-label">Kelas</span>
          <input
            class="input mt-1"
            placeholder="mis. 1A"
            bind:value={form.class_code}
            required
            aria-invalid={form.class_code.length > 0 && !classValid}
          />
        </label>
        <label class="block">
          <span class="mono-label">Tipe kelas</span>
          <select class="input mt-1" bind:value={form.class_type}>
            {#each classTypes as t}<option value={t}>{t}</option>{/each}
          </select>
        </label>
        <label class="block sm:col-span-2">
          <span class="mono-label">Deskripsi</span>
          <input
            class="input mt-1"
            placeholder="Ringkasan singkat pelajaran"
            bind:value={form.description}
          />
        </label>
      </div>

      <div class="mt-4 flex items-center justify-end gap-2 border-t pt-4">
        <a href="/teacher/subjects" class="btn-ghost">Batal</a>
        <button class="btn-primary" type="submit" disabled={!canSubmit}>
          {#if busy}<Icon name="spinner" spin size="12px" />{:else}<Icon
              name="plus"
              size="12px"
            />{/if}
          Buat pelajaran
        </button>
      </div>
    </form>

    <!-- Live preview -->
    <aside class="card h-fit lg:sticky lg:top-28">
      <p class="mono-label">Pratinjau</p>
      <div class="mt-3 flex items-center justify-between">
        <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
          <Icon name="book-open-reader" size="17px" />
        </span>
        <span class="badge badge-indigo">{classLabel}</span>
      </div>
      <h2 class="mt-3 font-display text-lg font-bold">
        {form.title.trim() || "Nama pelajaran"}
      </h2>
      {#if form.subject}<p class="mono-label mt-1">{form.subject}</p>{/if}
      <p class="mt-2 text-sm muted">{form.description.trim() || "Tanpa deskripsi"}</p>
      <p class="mono-label mt-3 border-t pt-3">
        <Icon name="book" size="10px" /> 0 materi
      </p>
      <p class="mt-3 flex items-start gap-1.5 text-xs muted">
        <Icon name="circle-info" size="11px" class="mt-0.5 flex-none" />
        Siswa di kelas <span class="font-medium text-ink">{form.class_code.trim() || "—"}</span> akan
        otomatis melihat pelajaran ini.
      </p>
    </aside>
  </div>
</div>
