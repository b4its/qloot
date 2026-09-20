<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";

  onMount(() => {
    if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");
  });

  let subjects: Course[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = false;

  // Create form
  let form = {
    title: "",
    subject: "",
    class_code: "1A",
    class_type: "IPA",
    description: "",
  };

  const classTypes = ["IPA", "IPS", "Bahasa", "Umum"];

  async function load() {
    loading = true;
    try {
      subjects = await api.get<Course[]>("/courses");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
    } finally {
      loading = false;
    }
  }

  async function create() {
    error = "";
    message = "";
    busy = true;
    try {
      const payload = {
        title: form.title.trim(),
        subject: form.subject.trim() || null,
        class_code: form.class_code.trim(),
        class_type: form.class_type || null,
        description: form.description.trim() || null,
      };
      await api.post<Course>("/courses", payload);
      message = "Pelajaran berhasil dibuat dan ditargetkan ke kelas.";
      form = { ...form, title: "", subject: "", description: "" };
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat pelajaran";
    } finally {
      busy = false;
    }
  }

  async function remove(s: Course) {
    if (!confirm(`Hapus pelajaran "${s.title}"?`)) return;
    try {
      await api.delete(`/courses/${s.id}`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus";
    }
  }

  async function togglePublish(s: Course) {
    try {
      await api.patch(`/courses/${s.id}`, { is_published: !s.is_published });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui";
    }
  }

  $: classes = [...new Set(subjects.map((s) => s.class_code).filter(Boolean))] as string[];

  onMount(load);
</script>

<svelte:head><title>Kelola Pelajaran — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panel Guru</p>
      <h1 class="mt-2 font-display text-4xl font-bold">Kelola Pelajaran</h1>
      <p class="mt-2 muted">
        Buat pelajaran, tentukan kelas dan tipe kelasnya. Siswa di kelas itu otomatis dapat
        mengaksesnya.
      </p>
    </div>
    <a href="/teacher" class="btn-ghost">← Panel Guru</a>
  </div>

  {#if message}
    <p class="mt-4 rounded-sm bg-secondary/10 p-3 text-sm text-secondary">
      <Icon name="circle-check" size="12px" class="mr-1" />
      {message}
    </p>
  {/if}
  {#if error}
    <p class="mt-4 rounded-sm bg-tertiary/10 p-3 text-sm text-tertiary">{error}</p>
  {/if}

  <!-- create form -->
  <div class="mt-6 grad-border">
    <div class="card">
      <h2 class="font-display text-lg font-bold">Buat pelajaran baru</h2>
      <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label class="block">
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
      <div class="mt-4 flex items-center justify-between">
        <p class="text-xs muted">
          <Icon name="circle-info" size="10px" /> Siswa di kelas {form.class_code || "—"} akan otomatis
          melihat pelajaran ini.
        </p>
        <button
          class="btn-primary"
          on:click={create}
          disabled={busy || form.title.trim().length < 2}
        >
          {#if busy}<Icon name="spinner" spin size="12px" />{:else}<Icon
              name="plus"
              size="12px"
            />{/if}
          Buat Pelajaran
        </button>
      </div>
    </div>
  </div>

  <!-- list -->
  <div class="mt-8">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="font-display text-xl font-bold">Pelajaran saya</h2>
      <div class="flex flex-wrap gap-2">
        {#each classes as c}<span class="badge badge-indigo">Kelas {c}</span>{/each}
      </div>
    </div>

    {#if loading}
      <div class="mt-4 space-y-3">
        {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
      </div>
    {:else if subjects.length === 0}
      <div class="card mt-4 grid place-items-center py-14 text-center">
        <Icon name="chalkboard-user" size="26px" class="muted" />
        <p class="mt-3 font-semibold">Belum ada pelajaran</p>
        <p class="text-sm muted">Buat pelajaran pertama dengan formulir di atas.</p>
      </div>
    {:else}
      <div class="mt-4 card !p-0 divide-y">
        {#each subjects as s}
          <div class="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
            <div class="flex items-center gap-4">
              <span
                class="grid h-11 w-11 place-items-center rounded-xl text-white"
                style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
              >
                <Icon name="book-open-reader" size="17px" />
              </span>
              <div>
                <div class="flex items-center gap-2">
                  <p class="font-semibold">{s.title}</p>
                  <span class="badge badge-indigo"
                    >Kelas {s.class_code}{s.class_type ? ` · ${s.class_type}` : ""}</span
                  >
                  {#if !s.is_published}<span class="badge badge-amber">Draf</span>{/if}
                </div>
                <p class="text-xs muted">
                  {s.subject ?? "Tanpa mata pelajaran"} · {s.lesson_count ?? 0} materi
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <a href={`/courses/${s.id}`} class="btn-ghost"
                ><Icon name="eye" size="12px" /> Lihat</a
              >
              <button class="btn-secondary" on:click={() => togglePublish(s)}>
                <Icon name={s.is_published ? "eye-slash" : "upload"} size="12px" />
                {s.is_published ? "Sembunyikan" : "Terbitkan"}
              </button>
              <button
                class="btn-ghost !text-tertiary"
                on:click={() => remove(s)}
                aria-label="Hapus"
              >
                <Icon name="trash" size="12px" />
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
