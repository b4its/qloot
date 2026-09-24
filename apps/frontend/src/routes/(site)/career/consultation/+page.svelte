<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Consultation, ConsultationMessage, Counselor } from "$lib/types";
  import { formatDate, statusLabel } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import { paginate } from "$lib/utils/format";

  const PAGE_SIZE = 10;
  let consultations: Consultation[] = [];
  let counselors: Counselor[] = [];
  let loading = true;
  let error = "";
  let form = { counselor_user_id: "", topic: "", notes: "" };
  let busy = false;
  let currentPage = 1;
  // CARE-06: the message thread for the consultation currently open.
  let openId = "";
  let thread: ConsultationMessage[] = [];
  let draft = "";
  $: totalPages = Math.max(1, Math.ceil(consultations.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedConsultations = paginate(consultations, currentPage, PAGE_SIZE);

  const statusBadge: Record<string, string> = {
    pending: "badge-amber",
    accepted: "badge-indigo",
    completed: "badge-mint",
    cancelled: "badge-magenta",
  };

  async function load() {
    loading = true;
    try {
      consultations = await api.get<Consultation[]>("/career/consultations?limit=200");
      counselors = await api.get<Counselor[]>("/career/counselors");
      if (counselors.length) form.counselor_user_id = counselors[0].user_id ?? "";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat konsultasi";
    } finally {
      loading = false;
    }
  }

  async function book() {
    busy = true;
    error = "";
    try {
      await api.post("/career/consultations", {
        counselor_user_id: form.counselor_user_id || null,
        counselor: form.counselor_user_id ? null : counselors[0]?.name,
        topic: form.topic,
        notes: form.notes,
      });
      form = { ...form, topic: "", notes: "" };
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memesan sesi";
    } finally {
      busy = false;
    }
  }

  async function cancel(c: Consultation) {
    error = "";
    try {
      await api.post(`/career/consultations/${c.id}/cancel`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membatalkan sesi";
    }
  }

  async function openThread(c: Consultation) {
    openId = c.id;
    try {
      thread = await api.get<ConsultationMessage[]>(
        `/career/consultations/${c.id}/messages`,
      );
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pesan";
    }
  }

  async function sendMessage() {
    if (!draft.trim() || !openId) return;
    try {
      await api.post(`/career/consultations/${openId}/messages`, { body: draft.trim() });
      draft = "";
      const c = consultations.find((x) => x.id === openId);
      if (c) await openThread(c);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim pesan";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Ruang Konseling (BK) — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Konsultasi</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Ruang Konseling (BK)</h1>
      <p class="mt-1 text-sm muted">Jadwalkan sesi dan pantau statusnya (simulasi).</p>
    </div>
    <a href="/career" class="btn-ghost">← Beranda karier</a>
  </div>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  <div class="mt-6 grid gap-4 lg:grid-cols-3">
    <div class="card lg:col-span-2">
      <h2 class="hud font-display text-lg font-bold">Sesimu</h2>
      {#if loading}
        <p class="mt-2 muted">Memuat …</p>
      {:else if !consultations.length}
        <p class="mt-2 muted">Belum ada sesi. Pesan sesi di panel kanan.</p>
      {:else}
        <ul class="mt-3 divide-y">
          {#each pagedConsultations as c}
            <li class="flex flex-wrap items-center justify-between gap-3 py-3">
              <div>
                <p class="font-medium">{c.topic}</p>
                <p class="text-xs muted">
                  {c.counselor} · {c.scheduled_at ? formatDate(c.scheduled_at) : "Belum ditentukan"}
                </p>
                {#if c.notes}<p class="text-xs muted">{c.notes}</p>{/if}
              </div>
              <div class="flex items-center gap-2">
                <span class={`badge ${statusBadge[c.status] ?? "badge-neutral"}`}
                  >{statusLabel(c.status)}</span
                >
                <button class="btn-ghost !py-1 text-xs" on:click={() => openThread(c)}>Pesan</button>
                {#if c.status === "pending"}
                  <button class="btn-ghost !py-1 text-xs" on:click={() => cancel(c)}>Batal</button>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
        <Pagination
          page={currentPage}
          pageSize={PAGE_SIZE}
          total={consultations.length}
          label="sesi"
          onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
          onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
        />
      {/if}

      {#if openId}
        <div class="mt-4 border-t pt-4">
          <div class="flex items-center justify-between">
            <p class="mono-label">Utas pesan</p>
            <button class="btn-ghost !py-1 text-xs" on:click={() => (openId = "")}>Tutup</button>
          </div>
          <ul class="mt-2 max-h-64 space-y-2 overflow-y-auto text-sm">
            {#each thread as m (m.id)}
              <li class="rounded-sm border p-2">{m.body}</li>
            {/each}
            {#if thread.length === 0}<li class="muted text-xs">Belum ada pesan.</li>{/if}
          </ul>
          <div class="mt-2 flex items-center gap-2">
            <label class="sr-only" for="consult-msg">Pesan konsultasi</label>
            <input
              id="consult-msg"
              class="input"
              bind:value={draft}
              placeholder="Tulis pesan…"
              on:keydown={(e) => e.key === "Enter" && sendMessage()}
            />
            <button class="btn-primary !py-1.5" on:click={sendMessage} disabled={!draft.trim()}>
              Kirim
            </button>
          </div>
        </div>
      {/if}
    </div>

    <div class="card h-fit">
      <h2 class="hud font-display text-lg font-bold">Pesan sesi</h2>
      <div class="mt-3 space-y-3">
        <label class="flex flex-col text-xs">
          <span class="muted mb-1">Pembimbing</span>
          <select class="input" bind:value={form.counselor_user_id}>
            {#each counselors as c}
              <option value={c.user_id ?? ""}>{c.name} — {c.role}</option>
            {/each}
          </select>
        </label>
        <input class="input" placeholder="Topik" bind:value={form.topic} />
        <textarea
          class="input min-h-[80px]"
          placeholder="Catatan (opsional)"
          bind:value={form.notes}
        ></textarea>
        <button class="btn-primary w-full" on:click={book} disabled={busy || form.topic.length < 2}>
          {busy ? "Memesan …" : "Ajukan sesi"}
        </button>
      </div>
      <div class="mt-4 border-t pt-3">
        <p class="mono-label">Pembimbing</p>
        <ul class="mt-2 space-y-2 text-sm">
          {#each counselors as c}
            <li>
              <p class="font-medium">{c.name}</p>
              <p class="text-xs muted">{c.role}</p>
            </li>
          {/each}
        </ul>
      </div>
    </div>
  </div>
</div>
