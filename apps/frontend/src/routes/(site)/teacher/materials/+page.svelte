<script lang="ts">
  import { api, ApiError } from "$lib/api/client";
  import type { Material, Question } from "$lib/types";
  import { formatDate } from "$lib/utils/format";

  let file: File | null = null;
  let uploading = false;
  let materials: Material[] = [];
  let message = "";
  let error = "";
  let generated: Question[] = [];
  let count = 3;
  let selected: Material | null = null;

  async function upload(e: Event) {
    e.preventDefault();
    if (!file) return;
    error = "";
    uploading = true;
    try {
      const form = new FormData();
      form.append("file", file);
      const material = await api.post<Material>("/materials/upload", form);
      message = `Uploaded ${material.filename}`;
      materials = [material, ...materials];
      file = null;
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Upload failed";
    } finally {
      uploading = false;
    }
  }

  async function generate(m: Material) {
    selected = m;
    generated = [];
    error = "";
    try {
      generated = await api.post<Question[]>(`/materials/${m.id}/generate-questions-sync`, {
        count,
        language: "id",
      });
      message = `Generated ${generated.length} draft questions — review before publishing.`;
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Generation failed";
    }
  }

  async function approve(q: Question) {
    await api.patch(`/questions/${q.id}`, { review_status: "approved" });
    generated = generated.map((g) => (g.id === q.id ? { ...g, review_status: "approved" } : g));
  }
</script>

<svelte:head><title>Materials — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Materials</h1>
<p class="mt-1 muted">Upload a PDF, then let AI draft essay questions from it.</p>

{#if message}<p class="mt-4 rounded-lg bg-primary/10 p-3 text-sm dark:bg-surface">
    {message}
  </p>{/if}
{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-tertiary dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

<form class="card mt-4" on:submit={upload}>
  <h2 class="font-semibold">Upload PDF</h2>
  <input
    class="input mt-3"
    type="file"
    accept="application/pdf"
    on:change={(e) => (file = (e.currentTarget as HTMLInputElement).files?.[0] ?? null)}
  />
  <button class="btn-primary mt-3" type="submit" disabled={!file || uploading}>
    {uploading ? "Uploading…" : "Upload"}
  </button>
</form>

{#if materials.length}
  <div class="card mt-4">
    <h2 class="font-semibold">Your materials</h2>
    <ul class="mt-2 space-y-2 text-sm">
      {#each materials as m}
        <li class="flex flex-wrap items-center justify-between gap-2 border-t pt-2">
          <span>
            <span class="font-medium">{m.filename}</span>
            <span class="block text-xs muted">{formatDate(m.created_at)}</span>
          </span>
          <span class="flex items-center gap-2">
            <input class="input w-16 !py-1" type="number" min="1" max="20" bind:value={count} />
            <button class="btn-ghost" on:click={() => generate(m)}>Generate questions</button>
          </span>
        </li>
      {/each}
    </ul>
  </div>
{/if}

{#if generated.length}
  <div class="card mt-4">
    <h2 class="font-semibold">Draft questions ({generated.length})</h2>
    <p class="text-xs muted">AI drafts await your review before they can be published.</p>
    <ol class="mt-3 space-y-3">
      {#each generated as q, i}
        <li class="border-t pt-2">
          <div class="flex items-start justify-between gap-3">
            <p class="font-medium">{i + 1}. {q.prompt}</p>
            <span
              class="badge"
              class:bg-green-100={q.review_status === "approved"}
              class:text-secondary={q.review_status === "approved"}>{q.review_status}</span
            >
          </div>
          <p class="mt-1 text-sm muted">Reference: {q.correct_answer}</p>
          {#if q.review_status !== "approved"}
            <button class="btn-ghost mt-2" on:click={() => approve(q)}>Approve</button>
          {/if}
        </li>
      {/each}
    </ol>
  </div>
{/if}
