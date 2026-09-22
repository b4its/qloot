<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let exams: Exam[] = [];
  let form = { title: "", exam_id: "", top_n_winners: 3, ranks: [100, 60, 40] };
  let busy = false;
  let error = "";
  let message = "";

  onMount(async () => {
    try {
      exams = await api.get<Exam[]>("/exams?limit=200");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    }
  });

  async function create() {
    error = "";
    message = "";
    busy = true;
    try {
      const rules = form.ranks.map((amount, i) => ({ rank: i + 1, reward_amount: amount }));
      const quest = await api.post<Quest>("/quests", {
        title: form.title,
        exam_id: form.exam_id || null,
        top_n_winners: form.top_n_winners,
        rules,
      });
      message = "Quest dibuat.";
      await goto(`/teacher/quests/${quest.id}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat quest";
      busy = false;
    }
  }
</script>

<svelte:head><title>Quest Baru — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Quest"
    title="Quest baru"
    subtitle="Tautkan ke ujian (opsional), tentukan jumlah pemenang, dan hadiah OPT per peringkat."
    backHref="/teacher/quests"
    backLabel="Quest"
  />

  <PageAlerts {message} {error} />

  <div class="card mt-6">
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="block sm:col-span-2">
        <span class="mono-label">Judul</span>
        <input class="input mt-1" placeholder="mis. Sprint Bab 1" bind:value={form.title} />
      </label>
      <label class="block sm:col-span-2">
        <span class="mono-label">Ujian tertaut</span>
        <select class="input mt-1" bind:value={form.exam_id}>
          <option value="">Tanpa ujian tertaut</option>
          {#each exams as e}<option value={e.id}>{e.title}</option>{/each}
        </select>
      </label>
      <label class="block">
        <span class="mono-label">Jumlah pemenang</span>
        <input class="input mt-1" type="number" min="1" max="50" bind:value={form.top_n_winners} />
      </label>
      <div class="block">
        <span class="mono-label">Hadiah OPT per peringkat</span>
        <div class="mt-1 flex items-center gap-2">
          {#each form.ranks as amount, i}
            <input class="input w-20" type="number" min="0" bind:value={form.ranks[i]} />
          {/each}
        </div>
      </div>
    </div>
  </div>

  <div class="mt-4 flex items-center justify-end gap-2">
    <a href="/teacher/quests" class="btn-ghost">Batal</a>
    <button class="btn-primary" on:click={create} disabled={busy || form.title.length < 2}>
      {busy ? "Membuat…" : "Buat quest"}
    </button>
  </div>
</div>
