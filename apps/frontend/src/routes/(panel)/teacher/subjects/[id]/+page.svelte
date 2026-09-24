<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Course, Lesson } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const courseId = $page.params.id;
  const classTypes = ["IPA", "IPS", "Bahasa", "Umum"];

  let course: Course | null = null;
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";

  let courseForm = {
    title: "",
    subject: "",
    class_code: "",
    class_type: "",
    description: "",
  };

  // Lesson management.
  let lessons: Lesson[] = [];
  let lessonsLoading = false;
  let newLesson = { title: "", content_md: "" };
  let editingLesson: string | null = null;
  let editLesson = { title: "", content_md: "" };

  async function loadCourse() {
    loading = true;
    try {
      course = await api.get<Course>(`/courses/${courseId}`);
      courseForm = {
        title: course.title,
        subject: course.subject ?? "",
        class_code: course.class_code ?? "",
        class_type: course.class_type ?? "",
        description: course.description ?? "",
      };
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
    } finally {
      loading = false;
    }
  }

  async function loadLessons() {
    lessonsLoading = true;
    try {
      lessons = await api.get<Lesson[]>(`/courses/${courseId}/lessons?limit=200`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat materi";
    } finally {
      lessonsLoading = false;
    }
  }

  async function saveCourse() {
    if (courseForm.title.trim().length < 2) {
      error = "Nama pelajaran minimal 2 karakter.";
      return;
    }
    error = "";
    message = "";
    busy = "course";
    try {
      course = await api.patch<Course>(`/courses/${courseId}`, {
        title: courseForm.title.trim(),
        subject: courseForm.subject.trim() || null,
        class_code: courseForm.class_code.trim(),
        class_type: courseForm.class_type || null,
        description: courseForm.description.trim() || null,
      });
      message = "Pelajaran diperbarui.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui pelajaran";
    } finally {
      busy = "";
    }
  }

  async function addLesson() {
    if (newLesson.title.trim().length < 2) {
      error = "Judul materi minimal 2 karakter.";
      return;
    }
    error = "";
    message = "";
    busy = "lesson-add";
    try {
      await api.post(`/courses/${courseId}/lessons`, {
        title: newLesson.title.trim(),
        content_md: newLesson.content_md.trim() || null,
        position: lessons.length,
      });
      newLesson = { title: "", content_md: "" };
      message = "Materi ditambahkan.";
      await loadLessons();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menambah materi";
    } finally {
      busy = "";
    }
  }

  function startEditLesson(l: Lesson) {
    editingLesson = l.id;
    editLesson = { title: l.title, content_md: l.content_md ?? "" };
  }

  async function saveLesson() {
    if (!editingLesson) return;
    if (editLesson.title.trim().length < 2) {
      error = "Judul materi minimal 2 karakter.";
      return;
    }
    error = "";
    busy = "lesson-edit";
    try {
      await api.patch(`/lessons/${editingLesson}`, {
        title: editLesson.title.trim(),
        content_md: editLesson.content_md.trim() || null,
      });
      editingLesson = null;
      message = "Materi diperbarui.";
      await loadLessons();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui materi";
    } finally {
      busy = "";
    }
  }

  async function removeLesson(l: Lesson) {
    if (!confirm(`Hapus materi "${l.title}"?`)) return;
    error = "";
    message = "";
    busy = `lesson-del-${l.id}`;
    try {
      await api.delete(`/lessons/${l.id}`);
      message = "Materi dihapus.";
      await loadLessons();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus materi";
    } finally {
      busy = "";
    }
  }

  async function moveLesson(index: number, delta: number) {
    const next = index + delta;
    if (next < 0 || next >= lessons.length) return;
    const ordered = lessons.map((l) => l.id);
    [ordered[index], ordered[next]] = [ordered[next], ordered[index]];
    error = "";
    message = "";
    busy = "lesson-reorder";
    try {
      await api.post(`/courses/${courseId}/lessons/reorder`, { lesson_ids: ordered });
      await loadLessons();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah urutan";
    } finally {
      busy = "";
    }
  }

  onMount(() => {
    loadCourse();
    loadLessons();
  });
</script>

<svelte:head><title>Kelola Pelajaran — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Pelajaran"
    title={course?.title ?? "Kelola pelajaran"}
    subtitle="Ubah detail pelajaran dan kelola materinya."
    backHref="/teacher/subjects"
    backLabel="Pelajaran"
  />

  <PageAlerts {message} {error} />

  {#if loading}
    <div class="mt-6 space-y-3">
      <div class="skeleton h-40"></div>
      <div class="skeleton h-40"></div>
    </div>
  {:else if course}
    <!-- course details -->
    <div class="card mt-6">
      <div class="flex items-center justify-between">
        <h2 class="hud font-display text-lg font-bold">Detail pelajaran</h2>
        {#if !course.is_published}<span class="badge badge-amber">Draf</span>{/if}
      </div>
      <div class="mt-3 grid gap-3 sm:grid-cols-2">
        <label class="block sm:col-span-2">
          <span class="mono-label">Nama pelajaran</span>
          <input class="input mt-1" bind:value={courseForm.title} />
        </label>
        <label class="block">
          <span class="mono-label">Mata pelajaran</span>
          <input class="input mt-1" bind:value={courseForm.subject} />
        </label>
        <label class="block">
          <span class="mono-label">Kelas</span>
          <input class="input mt-1" bind:value={courseForm.class_code} />
        </label>
        <label class="block">
          <span class="mono-label">Tipe kelas</span>
          <select class="input mt-1" bind:value={courseForm.class_type}>
            <option value="">—</option>
            {#each classTypes as t}<option value={t}>{t}</option>{/each}
          </select>
        </label>
        <label class="block sm:col-span-2">
          <span class="mono-label">Deskripsi</span>
          <input class="input mt-1" bind:value={courseForm.description} />
        </label>
      </div>
      <div class="mt-3 flex items-center justify-between">
        <a href={`/courses/${course.id}`} class="btn-ghost text-xs">
          <Icon name="eye" size="11px" /> Lihat sebagai siswa
        </a>
        <button
          class="btn-primary"
          on:click={saveCourse}
          disabled={busy === "course" || courseForm.title.trim().length < 2}
        >
          {busy === "course" ? "Menyimpan…" : "Simpan perubahan"}
        </button>
      </div>
    </div>

    <!-- lessons -->
    <div class="card mt-4">
      <h2 class="hud font-display text-lg font-bold">Materi ({lessons.length})</h2>
      {#if lessonsLoading}
        <div class="mt-3 space-y-2">
          {#each Array(2) as _}<div class="skeleton h-8"></div>{/each}
        </div>
      {:else}
        <ol class="mt-3 space-y-1 text-sm">
          {#each lessons as l, i}
            {#if editingLesson === l.id}
              <li class="border-b py-2 last:border-0">
                <input class="input" bind:value={editLesson.title} placeholder="Judul materi" />
                <textarea
                  class="input mt-2 min-h-[60px]"
                  placeholder="Konten (Markdown)"
                  bind:value={editLesson.content_md}
                ></textarea>
                <div class="mt-2 flex gap-2">
                  <button
                    class="btn-primary !py-1.5"
                    on:click={saveLesson}
                    disabled={busy === "lesson-edit"}>Simpan</button
                  >
                  <button class="btn-ghost !py-1.5" on:click={() => (editingLesson = null)}
                    >Batal</button
                  >
                </div>
              </li>
            {:else}
              <li class="flex items-center justify-between border-b py-1 last:border-0">
                <span>{i + 1}. {l.title}</span>
                <span class="flex items-center gap-2">
                  <span
                    class="badge"
                    class:badge-mint={l.is_published}
                    class:badge-neutral={!l.is_published}
                  >
                    {l.is_published ? "Terbit" : "Draf"}
                  </span>
                  <button
                    class="btn-icon"
                    on:click={() => startEditLesson(l)}
                    aria-label="Sunting materi"
                  >
                    <Icon name="pen" size="11px" />
                  </button>
                  <button
                    class="btn-icon"
                    on:click={() => moveLesson(i, -1)}
                    disabled={i === 0 || busy === "lesson-reorder"}
                    aria-label="Naikkan urutan"
                  >
                    <Icon name="arrow-up" size="11px" />
                  </button>
                  <button
                    class="btn-icon"
                    on:click={() => moveLesson(i, 1)}
                    disabled={i === lessons.length - 1 || busy === "lesson-reorder"}
                    aria-label="Turunkan urutan"
                  >
                    <Icon name="arrow-down" size="11px" />
                  </button>
                  <button
                    class="btn-icon !text-tertiary hover:!border-tertiary"
                    on:click={() => removeLesson(l)}
                    disabled={busy === `lesson-del-${l.id}`}
                    aria-label="Hapus materi"
                  >
                    <Icon name="trash" size="11px" />
                  </button>
                </span>
              </li>
            {/if}
          {/each}
          {#if lessons.length === 0}<li class="muted">Belum ada materi.</li>{/if}
        </ol>

        <div class="mt-3 space-y-2 border-t pt-3">
          <input class="input" placeholder="Judul materi baru" bind:value={newLesson.title} />
          <textarea
            class="input min-h-[70px]"
            placeholder="Konten (Markdown)"
            bind:value={newLesson.content_md}
          ></textarea>
          <button class="btn-primary" on:click={addLesson} disabled={busy === "lesson-add"}>
            {#if busy === "lesson-add"}<Icon name="spinner" spin size="12px" />{:else}<Icon
                name="plus"
                size="12px"
              />{/if}
            Tambah materi
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
