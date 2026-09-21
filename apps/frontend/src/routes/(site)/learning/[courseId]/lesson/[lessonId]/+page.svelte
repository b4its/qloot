<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Lesson } from "$lib/types";
  import Icon from "$lib/components/Icon.svelte";

  let lesson: Lesson | null = null;
  let loading = true;
  let error = "";
  let saving = false;
  let saved = false;

  const lessonId = $page.params.lessonId;

  async function load() {
    try {
      lesson = await api.get<Lesson>(`/lessons/${lessonId}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat materi";
    } finally {
      loading = false;
    }
  }

  async function complete() {
    if (!lesson) return;
    error = "";
    saving = true;
    try {
      await api.post(`/lessons/${lesson.id}/progress`, {
        progress_percent: 100,
        completed: true,
      });
      saved = true;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menandai selesai";
    } finally {
      saving = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>{lesson?.title ?? "Materi"} — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  {#if loading}
    <div class="space-y-3">
      <div class="skeleton h-6 w-40"></div>
      <div class="skeleton h-64"></div>
    </div>
  {:else if !lesson}
    <p class="alert-error">{error || "Materi tidak ditemukan."}</p>
  {:else}
    <a href={`/learning/${lesson.course_id}`} class="text-sm text-primary">← Kembali ke pelajaran</a
    >
    <article class="card mt-3">
      <p class="mono-label">Materi</p>
      <h1 class="mt-2 font-display text-3xl font-bold">{lesson.title}</h1>
      {#if lesson.video_url}
        <video class="mt-4 w-full rounded-sm border" controls src={lesson.video_url}>
          <track kind="captions" label="Captions" />
        </video>
      {/if}
      {#if lesson.content_md}
        <pre class="mt-4 whitespace-pre-wrap font-sans text-sm">{lesson.content_md}</pre>
      {:else}
        <p class="mt-4 muted">Belum ada konten.</p>
      {/if}

      {#if error}
        <p class="alert-error mt-4">{error}</p>
      {/if}

      {#if saved}
        <p class="alert-ok mt-6">
          <Icon name="circle-check" size="12px" /> Materi ditandai selesai.
        </p>
        <a href={`/learning/${lesson.course_id}`} class="btn-secondary mt-3"
          >Kembali ke daftar materi</a
        >
      {:else}
        <button class="btn-primary mt-6" on:click={complete} disabled={saving}>
          {#if saving}<Icon name="spinner" spin size="12px" />{/if}
          {saving ? "Menyimpan…" : "Tandai selesai"}
        </button>
      {/if}
    </article>
  {/if}
</div>
