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

  async function create() {
    error = "";
    message = "";
    if (form.title.trim().length < 2) {
      error = "Judul pelajaran minimal 2 karakter.";
      return;
    }
    if (form.class_code.trim().length < 1) {
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

  <div class="card mt-6">
    <div class="grid gap-4 sm:grid-cols-2">
      <label class="block sm:col-span-2">
        <span class="mono-label">Nama pelajaran</span>
        <input class="input mt-1" placeholder="mis. Matematika 1A" bind:value={form.title} />
      </label>
      <label class="block">
        <span class="mono-label">Mata pelajaran</span>
        <input class="input mt-1" placeholder="mis. Matematika" bind:value={form.subject} />
      </label>
      <label class="block">
        <span class="mono-label">Kelas</span>
        <input class="input mt-1" placeholder="mis. 1A" bind:value={form.class_code} />
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
  </div>

  <div class="mt-4 flex items-center justify-between">
    <p class="text-xs muted">
      <Icon name="circle-info" size="10px" />
      Siswa di kelas {form.class_code || "—"} akan otomatis melihat pelajaran ini.
    </p>
    <div class="flex gap-2">
      <a href="/teacher/subjects" class="btn-ghost">Batal</a>
      <button class="btn-primary" on:click={create} disabled={busy || form.title.trim().length < 2}>
        {#if busy}<Icon name="spinner" spin size="12px" />{:else}<Icon
            name="plus"
            size="12px"
          />{/if}
        Buat pelajaran
      </button>
    </div>
  </div>
</div>
