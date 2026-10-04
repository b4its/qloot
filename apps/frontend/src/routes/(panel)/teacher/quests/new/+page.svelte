<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Quest, Exam } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let exams: Exam[] = [];
  let form = { title: "", exam_id: "", top_n_winners: 3 };
  // Reward amounts keyed by rank (1-based). Kept in sync with the winner count
  // so every winner has a rule: otherwise a late-ranked winner gets no reward.
  let ranks: number[] = [100, 60, 40];
  let busy = false;
  let error = "";
  let message = "";

  onMount(() => {
    (async () => {
      try {
        exams = await api.get<Exam[]>("/exams?limit=200");
      } catch (e) {
        error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
      }
    })().catch((e) => {
      error = e instanceof ApiError ? e.message : "Gagal memuat ujian";
    });
  });

  const DEFAULT_RANKS = [100, 60, 40, 20, 10];

  function defaultAmount(rank: number): number {
    return DEFAULT_RANKS[rank - 1] ?? 5;
  }

  /** Grow/shrink the reward column count to match the winner count. */
  function syncRanks() {
    const n = Math.max(1, Math.min(50, Number(form.top_n_winners) || 1));
    form.top_n_winners = n;
    const next = ranks.slice(0, n);
    for (let r = next.length + 1; r <= n; r++) next.push(defaultAmount(r));
    // Reassign so Svelte re-renders the reward inputs.
    ranks = next;
  }

  $: totalPool = ranks.reduce((s, r) => s + r, 0);
  $: titleValid = form.title.trim().length >= 2;
  // Each winner must receive at least 1 OPT, otherwise the quest awards nothing.
  $: ranksValid = ranks.length > 0 && ranks.every((r) => r >= 1);
  // Reward budget preview (W3): the ledger refuses any single credit above the
  // per-transaction cap, so warn before the teacher authors an unrewardable
  // rank. The cap matches the backend default (opc_max_reward_per_tx).
  const PER_TX_CAP = 100_000;
  $: overCap = ranks.filter((r) => r > PER_TX_CAP);
  $: budgetOk = overCap.length === 0;
  $: canSubmit = titleValid && ranksValid && budgetOk && !busy;

  async function create() {
    error = "";
    message = "";
    if (!titleValid) {
      error = "Judul quest minimal 2 karakter.";
      return;
    }
    if (!(form.top_n_winners >= 1 && form.top_n_winners <= 50)) {
      error = "Jumlah pemenang harus antara 1 dan 50.";
      return;
    }
    if (!ranksValid) {
      error = "Hadiah tidak boleh negatif.";
      return;
    }
    if (!budgetOk) {
      error = `Hadiah per peringkat maksimal ${formatNumber(PER_TX_CAP)} OPT (batas per transaksi).`;
      return;
    }
    busy = true;
    try {
      const rules = ranks.map((amount, i) => ({ rank: i + 1, reward_amount: amount }));
      const quest = await api.post<Quest>("/quests", {
        title: form.title.trim(),
        exam_id: form.exam_id || null,
        top_n_winners: form.top_n_winners,
        rules,
      });
      message = "Quest dibuat.";
      await goto(`/teacher/quests/${quest.id}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat quest";
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head><title>Quest Baru | Panel Guru | QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Quest"
    title="Quest baru"
    subtitle="Tautkan ke ujian (opsional), tentukan jumlah pemenang, dan hadiah OPT per peringkat."
    backHref="/teacher/quests"
    backLabel="Quest"
  />

  <PageAlerts {message} {error} />

  <div class="mt-6 grid gap-4 lg:grid-cols-[1fr_300px]">
    <form class="card" on:submit|preventDefault={create} aria-label="Form quest baru">
      <p class="mono-label">Detail quest</p>
      <div class="mt-2 grid gap-3 sm:grid-cols-2">
        <label class="block sm:col-span-2">
          <span class="mono-label">Judul</span>
          <input
            class="input mt-1"
            placeholder="mis. Sprint Bab 1"
            bind:value={form.title}
            required
            aria-invalid={form.title.length > 0 && !titleValid}
          />
          {#if form.title.length > 0 && !titleValid}
            <span class="mt-1 block text-[11px] text-danger">Minimal 2 karakter.</span>
          {/if}
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
          <input
            class="input mt-1"
            type="number"
            min="1"
            max="50"
            bind:value={form.top_n_winners}
            on:input={syncRanks}
          />
        </label>
      </div>

      <div class="mt-4">
        <div class="flex items-center justify-between">
          <span class="mono-label">Hadiah OPT per peringkat</span>
          <span class="mono-label text-[10px]">Total pool: {formatNumber(totalPool)} OPT</span>
        </div>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          {#each ranks as amount, i (i)}
            <label class="flex items-center gap-1 rounded-sm border px-2 py-1">
              <span class="badge badge-amber">#{i + 1}</span>
              <input
                class="input w-20 !py-1 text-sm"
                type="number"
                min="1"
                aria-label={`Hadiah peringkat ${i + 1}`}
                aria-invalid={ranks[i] < 1}
                bind:value={ranks[i]}
              />
            </label>
          {/each}
        </div>
        {#if !ranksValid && ranks.some((r) => r < 1)}
          <p class="mt-2 text-xs text-danger" role="alert">
            Setiap peringkat pemenang harus mendapat minimal 1 OPT.
          </p>
        {/if}
        {#if !budgetOk}
          <p class="mt-2 text-xs text-danger" role="alert" data-role="budget-warning">
            Hadiah per peringkat maksimal {formatNumber(PER_TX_CAP)} OPT (batas per transaksi on-chain).
            Turunkan peringkat #{overCap.length > 0 ? ranks.indexOf(overCap[0]) + 1 : ""}.
          </p>
        {/if}
        <div class="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span class="badge badge-mint" data-role="budget-pool">
            Total pool {formatNumber(totalPool)} OPT
          </span>
          <span class="badge {budgetOk ? 'badge-neutral' : 'badge-magenta'}">
            Maks/peringkat {formatNumber(Math.max(0, ...ranks))} OPT
          </span>
          <span class="badge badge-neutral">Plafon {formatNumber(PER_TX_CAP)} OPT</span>
        </div>
        <p class="mt-2 text-xs muted">
          <Icon name="circle-info" size="10px" />
          Kolom hadiah otomatis mengikuti jumlah pemenang. Pemenang ditentukan deterministik (skor, lalu
          kecepatan).
        </p>
      </div>

      <div class="mt-5 flex items-center justify-end gap-2 border-t pt-4">
        <a href="/teacher/quests" class="btn-ghost">Batal</a>
        <button class="btn-primary" type="submit" disabled={!canSubmit}>
          {busy ? "Membuat…" : "Buat quest"}
        </button>
      </div>
    </form>

    <!-- Live preview -->
    <aside class="card h-fit lg:sticky lg:top-28">
      <p class="mono-label">Pratinjau</p>
      <div class="mt-3 flex items-center justify-between">
        <span class="tile h-11 w-11"><Icon name="trophy" size="18px" /></span>
        <span class="badge badge-indigo">Top {form.top_n_winners}</span>
      </div>
      <h2 class="mt-3 font-display text-lg font-bold">{form.title.trim() || "Judul quest"}</h2>
      <p class="mt-1 text-xs muted">
        {form.exam_id ? "Ujian tertaut" : "Tanpa ujian tertaut"} · {formatNumber(totalPool)} OPT
      </p>
      <ul class="mt-3 space-y-1 border-t pt-3 text-sm">
        {#each ranks as amount, i (i)}
          <li class="flex items-center justify-between">
            <span class="muted">Peringkat #{i + 1}</span>
            <span class="font-mono">{formatNumber(amount)} OPT</span>
          </li>
        {/each}
      </ul>
    </aside>
  </div>
</div>
