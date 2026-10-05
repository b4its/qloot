<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Winner } from "$lib/types";
  import { bpToPercent, formatDate, formatNumber, statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import CoinIcon from "$lib/components/CoinIcon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const questId = $page.params.id;

  let quest: Quest | null = null;
  let winners: Winner[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let form = {
    title: "",
    description: "",
    top_n_winners: 3,
    opens_at: "",
    closes_at: "",
  };
  // Publishing makes the quest visible/competable; confirm it.
  let confirmingPublish = false;

  /** Convert an ISO timestamp to the `datetime-local` input format. */
  function toLocalInput(iso: string | null | undefined): string {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  async function load() {
    loading = true;
    try {
      quest = await api.get<Quest>(`/quests/${questId}`);
      form = {
        title: quest.title,
        description: quest.description ?? "",
        top_n_winners: quest.top_n_winners,
        opens_at: toLocalInput(quest.opens_at),
        closes_at: toLocalInput(quest.closes_at),
      };
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
    if (!(form.top_n_winners >= 1 && form.top_n_winners <= 50)) {
      error = "Jumlah pemenang harus antara 1 dan 50.";
      return;
    }
    if (form.opens_at && form.closes_at && form.closes_at <= form.opens_at) {
      error = "Waktu tutup harus setelah waktu buka.";
      return;
    }
    error = "";
    message = "";
    busy = "save";
    try {
      quest = await api.patch<Quest>(`/quests/${questId}`, {
        title: form.title.trim(),
        description: form.description.trim() || null,
        top_n_winners: form.top_n_winners,
        opens_at: form.opens_at ? new Date(form.opens_at).toISOString() : null,
        closes_at: form.closes_at ? new Date(form.closes_at).toISOString() : null,
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
    confirmingPublish = false;
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

  // --- derived ---------------------------------------------------------------
  $: rules = quest?.rules ?? [];
  $: totalPool = rules.reduce((s, r) => s + r.reward_amount, 0);
  $: titleValid = form.title.trim().length >= 2;
  $: winnersValid = form.top_n_winners >= 1 && form.top_n_winners <= 50;
  $: windowValid = !form.opens_at || !form.closes_at || form.closes_at > form.opens_at;
  $: canSave =
    titleValid &&
    winnersValid &&
    windowValid &&
    dirty &&
    busy !== "save" &&
    quest?.status !== "finalized";
  $: dirty =
    !!quest &&
    (form.title.trim() !== quest.title ||
      form.description.trim() !== (quest.description ?? "") ||
      form.top_n_winners !== quest.top_n_winners ||
      form.opens_at !== toLocalInput(quest.opens_at) ||
      form.closes_at !== toLocalInput(quest.closes_at));
</script>

<svelte:head><title>Kelola Quest | Panel Guru | QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
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
      <div class="skeleton h-24"></div>
    </div>
  {:else if quest}
    <div class="mt-6 grid gap-4 lg:grid-cols-[1fr_300px]">
      <form class="card" on:submit|preventDefault={save} aria-label="Form ubah quest">
        <div class="flex items-center justify-between">
          <h2 class="hud font-display text-lg font-bold">Detail quest</h2>
          <span
            class="badge"
            class:badge-mint={quest.status === "open"}
            class:badge-indigo={quest.status === "finalized"}
            class:badge-neutral={quest.status === "draft"}>{statusLabel(quest.status)}</span
          >
        </div>
        <div class="mt-3 grid gap-3 sm:grid-cols-2">
          <label class="block sm:col-span-2">
            <span class="mono-label">Judul</span>
            <input
              class="input mt-1"
              bind:value={form.title}
              aria-invalid={form.title.length > 0 && !titleValid}
            />
            {#if form.title.length > 0 && !titleValid}
              <span class="mt-1 block text-[11px] text-danger">Minimal 2 karakter.</span>
            {/if}
          </label>
          <label class="block">
            <span class="mono-label">Jumlah pemenang</span>
            <input
              class="input mt-1"
              type="number"
              min="1"
              max="50"
              bind:value={form.top_n_winners}
              aria-invalid={!winnersValid}
            />
            {#if !winnersValid}
              <span class="mt-1 block text-[11px] text-danger">Harus antara 1 dan 50.</span>
            {/if}
          </label>
          <div class="block">
            <span class="mono-label">Jenis</span>
            <p class="mt-1 font-medium">{quest.kind}</p>
          </div>
          <label class="block sm:col-span-2">
            <span class="mono-label">Deskripsi</span>
            <textarea
              class="input mt-1 min-h-[72px]"
              placeholder="Ringkasan aturan / tujuan quest"
              bind:value={form.description}
            ></textarea>
          </label>
          <label class="block">
            <span class="mono-label">Dibuka (opsional)</span>
            <input class="input mt-1" type="datetime-local" bind:value={form.opens_at} />
          </label>
          <label class="block">
            <span class="mono-label">Ditutup (opsional)</span>
            <input
              class="input mt-1"
              type="datetime-local"
              bind:value={form.closes_at}
              aria-invalid={!windowValid}
            />
            {#if !windowValid}
              <span class="mt-1 block text-[11px] text-danger"> Harus setelah waktu buka. </span>
            {/if}
          </label>
        </div>
        <div class="mt-4 flex items-center justify-end gap-2 border-t pt-4">
          {#if quest.status === "draft"}
            <button
              type="button"
              class="btn-secondary mr-auto"
              on:click={() => (confirmingPublish = true)}
              disabled={busy === "publish"}
            >
              <Icon name="upload" size="11px" />
              {busy === "publish" ? "Menerbitkan…" : "Terbitkan"}
            </button>
          {/if}
          <a href="/teacher/quests" class="btn-ghost">Kembali</a>
          <button class="btn-primary" type="submit" disabled={!canSave}>
            {busy === "save" ? "Menyimpan…" : dirty ? "Simpan perubahan" : "Tersimpan"}
          </button>
        </div>
      </form>

      <aside class="space-y-4 h-fit lg:sticky lg:top-28">
        <!-- Reward rules -->
        <div class="card">
          <div class="flex items-center justify-between">
            <p class="mono-label">Hadiah per peringkat</p>
            <span class="mono-label text-[10px] flex items-center gap-1"
              ><CoinIcon size="11px" /> {formatNumber(totalPool)} OPT</span
            >
          </div>
          {#if rules.length === 0}
            <p class="mt-2 text-xs muted">Belum ada aturan hadiah.</p>
          {:else}
            <ul class="mt-2 space-y-1 text-sm">
              {#each rules as r (r.rank)}
                <li class="flex items-center justify-between border-b py-1 last:border-0">
                  <span class="badge badge-amber">#{r.rank}</span>
                  <span class="font-mono flex items-center gap-1"
                    ><CoinIcon size="12px" /> {formatNumber(r.reward_amount)} OPT</span
                  >
                </li>
              {/each}
            </ul>
          {/if}
          <p class="mt-2 text-[11px] muted">
            Pemenang ditentukan deterministik (skor, lalu kecepatan).
          </p>
        </div>

        <!-- Metadata -->
        <div class="card">
          <p class="mono-label">Metadata</p>
          <dl class="mt-2 space-y-1 text-xs">
            <div class="flex justify-between">
              <dt class="muted">Dibuka</dt>
              <dd>{quest.opens_at ? formatDate(quest.opens_at) : "-"}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="muted">Ditutup</dt>
              <dd>{quest.closes_at ? formatDate(quest.closes_at) : "-"}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="muted">Difinalisasi</dt>
              <dd>{quest.finalized_at ? formatDate(quest.finalized_at) : "-"}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="muted">Versi hadiah</dt>
              <dd class="font-mono">v{quest.reward_version}</dd>
            </div>
          </dl>
        </div>
      </aside>
    </div>

    {#if quest.status === "finalized"}
      <div class="card mt-4">
        <h2 class="hud font-display text-lg font-bold">Pemenang</h2>
        {#if winners.length === 0}
          <p class="mt-2 text-sm muted">Tidak ada pemenang tercatat.</p>
        {:else}
          <ol class="mt-2 space-y-1 text-sm">
            {#each winners as w (w.user_id)}
              <li class="flex justify-between border-b pb-1 last:border-0">
                <span>#{w.rank} · <span class="font-mono">{w.user_id.slice(0, 8)}…</span></span>
                <span>{bpToPercent(w.score_bp)} · {formatNumber(w.reward_amount)} OPT</span>
              </li>
            {/each}
          </ol>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<!-- Publish confirmation modal -->
{#if confirmingPublish}
  <ConfirmDialog
    title="Terbitkan Quest"
    description={`Terbitkan quest "${quest?.title}"? Setelah diterbitkan, siswa dapat mulai berkompetisi dan tidak bisa dikembalikan ke draf.`}
    confirmLabel="Ya, Terbitkan"
    busy={busy === "publish"}
    confirmRole="confirm-publish"
    onConfirm={publish}
    close={() => (confirmingPublish = false)}
  />
{/if}
