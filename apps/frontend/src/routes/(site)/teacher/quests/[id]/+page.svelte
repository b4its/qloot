<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Winner } from "$lib/types";
  import { bpToPercent, statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const questId = $page.params.id;

  let quest: Quest | null = null;
  let winners: Winner[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let form = { title: "", top_n_winners: 3 };

  async function load() {
    loading = true;
    try {
      quest = await api.get<Quest>(`/quests/${questId}`);
      form = { title: quest.title, top_n_winners: quest.top_n_winners };
      if (quest.status === "finalized") {
        winners = await api.get<Winner[]>(`/quests/${questId}/winners`);
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat quest";
    } finally {
      loading = false;
    }
  }

  async function save() {
    if (form.title.trim().length < 2) {
      error = "Judul quest minimal 2 karakter.";
      return;
    }
    error = "";
    message = "";
    busy = "save";
    try {
      quest = await api.patch<Quest>(`/quests/${questId}`, {
        title: form.title.trim(),
        top_n_winners: form.top_n_winners,
      });
      message = "Quest diperbarui.";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui quest";
    } finally {
      busy = "";
    }
  }

  async function publish() {
    error = "";
    message = "";
    busy = "publish";
    try {
      await api.post<Quest>(`/quests/${questId}/publish`);
      message = "Quest diterbitkan.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menerbitkan quest";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Kelola Quest — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Quest"
    title={quest?.title ?? "Kelola quest"}
    subtitle="Ubah detail quest. Finalisasi pemenang dilakukan dari daftar quest."
    backHref="/teacher/quests"
    backLabel="Quest"
  />

  <PageAlerts {message} {error} />

  {#if loading}
    <div class="mt-6 space-y-3">
      <div class="skeleton h-40"></div>
    </div>
  {:else if quest}
    <div class="card mt-6">
      <div class="flex items-center justify-between">
        <h2 class="hud font-display text-lg font-bold">Detail quest</h2>
        <span class="badge badge-neutral">{statusLabel(quest.status)}</span>
      </div>
      <div class="mt-3 grid gap-3 sm:grid-cols-2">
        <label class="block sm:col-span-2">
          <span class="mono-label">Judul</span>
          <input class="input mt-1" bind:value={form.title} />
        </label>
        <label class="block">
          <span class="mono-label">Jumlah pemenang</span>
          <input
            class="input mt-1"
            type="number"
            min="1"
            max="50"
            bind:value={form.top_n_winners}
          />
        </label>
      </div>
      <div class="mt-3 flex items-center justify-between">
        {#if quest.status === "draft"}
          <button class="btn-secondary" on:click={publish} disabled={busy === "publish"}>
            {busy === "publish" ? "Menerbitkan…" : "Terbitkan"}
          </button>
        {:else}<span></span>{/if}
        <button
          class="btn-primary"
          on:click={save}
          disabled={busy === "save" || quest.status === "finalized"}
        >
          {busy === "save" ? "Menyimpan…" : "Simpan perubahan"}
        </button>
      </div>
    </div>

    {#if quest.status === "finalized"}
      <div class="card mt-4">
        <h2 class="hud font-display text-lg font-bold">Pemenang</h2>
        {#if winners.length === 0}
          <p class="mt-2 text-sm muted">Tidak ada pemenang tercatat.</p>
        {:else}
          <ol class="mt-2 space-y-1 text-sm">
            {#each winners as w}
              <li class="flex justify-between border-b pb-1 last:border-0">
                <span>#{w.rank} · <span class="font-mono">{w.user_id.slice(0, 8)}…</span></span>
                <span>{bpToPercent(w.score_bp)} · {w.reward_amount} OPC</span>
              </li>
            {/each}
          </ol>
        {/if}
      </div>
    {/if}
  {/if}
</div>
