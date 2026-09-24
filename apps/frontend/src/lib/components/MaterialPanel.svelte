<script lang="ts">
  import { api, ApiError, API_BASE } from "$lib/api/client";
  import type { Material, SummaryResult, AskResult } from "$lib/types";
  import Icon from "$lib/components/Icon.svelte";

  /** Lesson whose attached materials should be listed. Required. */
  export let lessonId: string;

  let materials: Material[] = [];
  let loading = true;
  let error = "";

  // Per-material AI panel state, keyed by material id.
  let openId: string | null = null;
  let summaries: Record<string, SummaryResult> = {};
  let summaryLoading: Record<string, boolean> = {};
  let questionDrafts: Record<string, string> = {};
  let asking: Record<string, boolean> = {};
  let asks: Record<string, { q: string; a: AskResult }[]> = {};
  let askErrors: Record<string, string> = {};

  async function load() {
    loading = true;
    error = "";
    try {
      materials = await api.get<Material[]>(`/lessons/${lessonId}/materials?limit=200`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat materi";
    } finally {
      loading = false;
    }
  }

  function toggle(id: string) {
    openId = openId === id ? null : id;
  }

  async function summarize(id: string) {
    summaryLoading = { ...summaryLoading, [id]: true };
    try {
      summaries = { ...summaries, [id]: await api.get<SummaryResult>(`/materials/${id}/summary`) };
    } catch (e) {
      askErrors = {
        ...askErrors,
        [id]: e instanceof ApiError ? e.message : "Gagal merangkum materi",
      };
    } finally {
      summaryLoading = { ...summaryLoading, [id]: false };
    }
  }

  async function ask(id: string) {
    const question = (questionDrafts[id] ?? "").trim();
    if (question.length < 3) return;
    asking = { ...asking, [id]: true };
    askErrors = { ...askErrors, [id]: "" };
    try {
      const a = await api.post<AskResult>(`/materials/${id}/ask`, { question });
      asks = { ...asks, [id]: [{ q: question, a }, ...(asks[id] ?? [])] };
      questionDrafts = { ...questionDrafts, [id]: "" };
    } catch (e) {
      askErrors = {
        ...askErrors,
        [id]: e instanceof ApiError ? e.message : "Gagal menanyakan materi",
      };
    } finally {
      asking = { ...asking, [id]: false };
    }
  }

  load();
</script>

<div class="card mt-4" data-testid="material-panel">
  <h2 class="hud font-display text-lg font-bold">Materi</h2>
  <p class="mt-1 text-xs muted">
    Unduh PDF, minta ringkasan AI, atau tanyakan sesuatu tentang materi.
  </p>

  {#if loading}
    <div class="mt-3 space-y-2">
      <div class="skeleton h-10"></div>
    </div>
  {:else if error}
    <p class="alert-error mt-3">{error}</p>
  {:else if materials.length === 0}
    <p class="mt-3 muted">Belum ada materi PDF untuk pelajaran ini.</p>
  {:else}
    <ul class="mt-3 space-y-3">
      {#each materials as m}
        <li class="border-t pt-3">
          <div class="flex items-center justify-between gap-3">
            <p class="font-medium">{m.filename}</p>
            <div class="flex items-center gap-2">
              <a
                class="btn-ghost !py-1 text-xs"
                href={`${API_BASE}/api/v1/materials/${m.id}/download`}
                target="_blank"
                rel="noopener"
              >
                <Icon name="download" size="11px" /> Unduh
              </a>
              <button class="btn-secondary !py-1 text-xs" on:click={() => toggle(m.id)}>
                <Icon name="wand-magic-sparkles" size="11px" />
                {openId === m.id ? "Tutup" : "Asisten"}
              </button>
            </div>
          </div>

          {#if m.extraction_status === "empty"}
            <p class="alert-error mt-2 text-xs" role="alert">
              <Icon name="triangle-exclamation" size="11px" /> PDF ini tampaknya hasil pindai tanpa teks
              — ringkasan/tanya-jawab mungkin tidak akurat.
            </p>
          {/if}

          {#if openId === m.id}
            <div class="mt-3 rounded-sm border p-3">
              <button
                class="btn-secondary !py-1 text-xs"
                on:click={() => summarize(m.id)}
                disabled={summaryLoading[m.id]}
              >
                {#if summaryLoading[m.id]}<Icon name="spinner" spin size="11px" />{:else}<Icon
                    name="wand-magic-sparkles"
                    size="11px"
                  />{/if}
                Ringkas materi
              </button>

              {#if summaries[m.id]}
                <div class="alert-info mt-2 text-sm">
                  <strong>Ringkasan:</strong>
                  {summaries[m.id].summary}
                </div>
                {#if summaries[m.id].key_points?.length}
                  <ul class="mt-2 space-y-1 text-sm">
                    {#each summaries[m.id].key_points as kp}
                      <li class="flex items-start gap-2">
                        <Icon name="circle-check" class="mt-0.5 text-secondary" size="11px" />
                        {kp}
                      </li>
                    {/each}
                  </ul>
                {/if}
              {/if}

              <div class="mt-3 flex items-center gap-2">
                <input
                  class="input"
                  placeholder="Tanyakan sesuatu tentang materi ini…"
                  bind:value={questionDrafts[m.id]}
                  on:keydown={(e) => e.key === "Enter" && ask(m.id)}
                />
                <button
                  class="btn-primary flex-none !py-1.5 text-xs"
                  on:click={() => ask(m.id)}
                  disabled={asking[m.id] || (questionDrafts[m.id] ?? "").trim().length < 3}
                >
                  {#if asking[m.id]}<Icon name="spinner" spin size="12px" />{:else}<Icon
                      name="paper-plane"
                      size="12px"
                    />{/if}
                  Tanya
                </button>
              </div>

              {#if askErrors[m.id]}
                <p class="alert-error mt-2 text-xs">{askErrors[m.id]}</p>
              {/if}

              {#each asks[m.id] ?? [] as item}
                <div class="mt-3 border-t pt-2 text-sm">
                  <p class="font-medium">{item.q}</p>
                  <p class="mt-1 text-ink2">{item.a.answer}</p>
                  <p class="mono-label mt-1">Keyakinan {Math.round(item.a.confidence_bp / 100)}%</p>
                </div>
              {/each}
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>
