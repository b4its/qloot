<script lang="ts">
  import { onMount } from "svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Consultation, ConsultationMessage, Counselor } from "$lib/types";
  import { formatDate, statusLabel } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import { auth } from "$lib/stores/auth";
  import { paginate } from "$lib/utils/format";

  const PAGE_SIZE = 10;
  let consultations: Consultation[] = [];
  let counselors: Counselor[] = [];
  let loading = true;
  let error = "";
  let form = { counselor_user_id: "", topic: "", notes: "" };
  let busy = false;
  let currentPage = 1;
  let statusFilter: "all" | "pending" | "accepted" | "completed" | "cancelled" = "all";
  // CARE-06: the message thread for the consultation currently open.
  let openId = "";
  let thread: ConsultationMessage[] = [];
  let draft = "";
  let sendingMessage = false;
  let confirmingCancel: Consultation | null = null;

  $: activeConsultation = consultations.find((x) => x.id === openId);

  // --- derived metrics + filtering -------------------------------------------
  $: pendingCount = consultations.filter((c) => c.status === "pending").length;
  $: acceptedCount = consultations.filter((c) => c.status === "accepted").length;
  $: completedCount = consultations.filter((c) => c.status === "completed").length;

  $: filtered = consultations.filter((c) => statusFilter === "all" || c.status === statusFilter);
  $: totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: pagedConsultations = paginate(filtered, currentPage, PAGE_SIZE);

  const statusBadge: Record<string, string> = {
    pending: "badge-amber",
    accepted: "badge-indigo",
    completed: "badge-mint",
    cancelled: "badge-magenta",
  };

  type StatusFilter = "all" | "pending" | "accepted" | "completed" | "cancelled";
  const STATUS_TABS: { value: StatusFilter; label: string }[] = [
    { value: "all", label: "Semua" },
    { value: "pending", label: "Menunggu" },
    { value: "accepted", label: "Diterima" },
    { value: "completed", label: "Selesai" },
    { value: "cancelled", label: "Dibatalkan" },
  ];

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
    confirmingCancel = null;
    try {
      await api.post(`/career/consultations/${c.id}/cancel`);
      if (openId === c.id) openId = "";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membatalkan sesi";
    }
  }

  async function openThread(c: Consultation) {
    openId = c.id;
    try {
      thread = await api.get<ConsultationMessage[]>(`/career/consultations/${c.id}/messages`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pesan";
    }
  }

  async function sendMessage() {
    if (!draft.trim() || !openId || sendingMessage) return;
    sendingMessage = true;
    try {
      await api.post(`/career/consultations/${openId}/messages`, { body: draft.trim() });
      draft = "";
      const c = consultations.find((x) => x.id === openId);
      if (c) await openThread(c);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim pesan";
    } finally {
      sendingMessage = false;
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
    <p class="alert-error mt-4" role="alert" aria-live="assertive">
      {error}
    </p>
  {/if}

  <!-- Metrics -->
  {#if !loading && consultations.length > 0}
    <div class="mt-6 grid grid-cols-3 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total</p>
        <p class="mt-1 font-display text-3xl font-bold">{consultations.length}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Menunggu</p>
        <p class="mt-1 font-display text-3xl font-bold text-highlight" data-role="pending-count">
          {pendingCount}
        </p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Diterima</p>
        <p class="mt-1 font-display text-3xl font-bold text-primary">{acceptedCount}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Selesai</p>
        <p class="mt-1 font-display text-3xl font-bold text-mint">{completedCount}</p>
      </div>
    </div>

    <!-- Status tabs -->
    <div
      class="mt-4 flex flex-wrap gap-1 rounded-sm border p-1 w-fit"
      role="tablist"
      aria-label="Status sesi"
    >
      {#each STATUS_TABS as t (t.value)}
        <button
          role="tab"
          aria-selected={statusFilter === t.value}
          class="btn-ghost !px-3 !py-1.5 text-xs"
          class:bg-primary={statusFilter === t.value}
          class:!text-white={statusFilter === t.value}
          on:click={() => {
            statusFilter = t.value;
            currentPage = 1;
          }}
        >
          {t.label}
        </button>
      {/each}
    </div>
  {/if}

  <div class="mt-6 grid gap-4 lg:grid-cols-3">
    <div class="card lg:col-span-2">
      <h2 class="hud font-display text-lg font-bold">Sesimu</h2>
      {#if loading}
        <Skeleton rows={4} />
      {:else if !consultations.length}
        <p class="mt-2 muted">Belum ada sesi. Pesan sesi di panel kanan.</p>
      {:else if !filtered.length}
        <p class="mt-2 muted">Tidak ada sesi dengan status ini.</p>
      {:else}
        <ul class="mt-3 divide-y">
          {#each pagedConsultations as c (c.id)}
            <li
              class="flex flex-wrap items-center justify-between gap-3 py-3 rounded-lg hover:bg-surface-elevated/30 px-2 transition-colors"
            >
              <div>
                <p class="font-semibold text-sm">{c.topic}</p>
                <p class="text-xs muted mt-0.5 flex items-center gap-2">
                  <span>Pembimbing: {c.counselor}</span>
                  <span>·</span>
                  <span class="inline-flex items-center gap-1">
                    <Icon name="calendar" size="10px" />
                    {c.scheduled_at ? formatDate(c.scheduled_at) : "Belum ditentukan"}
                  </span>
                </p>
                {#if c.notes}<p class="text-xs muted mt-1 italic">"{c.notes}"</p>{/if}
              </div>
              <div class="flex items-center gap-2">
                <span class={`badge ${statusBadge[c.status] ?? "badge-neutral"}`}
                  >{statusLabel(c.status)}</span
                >
                <button class="btn-ghost !py-1 text-xs" on:click={() => openThread(c)}>
                  <Icon name="comments" size="11px" /> Pesan
                </button>
                {#if c.status === "pending"}
                  <button
                    class="btn-ghost !py-1 text-xs !text-danger hover:!bg-danger/10"
                    on:click={() => (confirmingCancel = c)}
                  >
                    Batal
                  </button>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
        <Pagination
          page={currentPage}
          pageSize={PAGE_SIZE}
          total={filtered.length}
          label="sesi"
          onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
          onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
        />
      {/if}

      {#if openId}
        <div class="mt-4 border-t pt-4">
          <div class="flex items-center justify-between pb-3 border-b">
            <div>
              <p class="mono-label text-primary">Percakapan Konseling</p>
              <h3 class="font-bold text-sm">
                {activeConsultation?.topic || "Sesi Konseling"}
                {#if activeConsultation?.counselor}
                  <span class="text-xs muted font-normal ml-1"
                    >· Pembimbing: {activeConsultation.counselor}</span
                  >
                {/if}
              </h3>
            </div>
            <button class="btn-ghost !py-1 text-xs" on:click={() => (openId = "")}>
              <Icon name="xmark" size="11px" /> Tutup
            </button>
          </div>

          <div class="mt-3 max-h-80 space-y-3 overflow-y-auto px-1 py-2">
            {#if thread.length === 0}
              <div class="text-center py-8">
                <p class="text-xs muted">
                  Belum ada pesan. Sampaikan pertanyaan atau detail masalahmu ke pembimbing.
                </p>
              </div>
            {:else}
              {#each thread as m (m.id)}
                {@const isMe = m.sender_id === $auth.user?.id}
                <div class="flex flex-col {isMe ? 'items-end' : 'items-start'}">
                  <div class="flex items-center gap-1.5 mb-0.5 text-[11px] muted">
                    <span class="font-semibold {isMe ? 'text-primary' : 'text-neutral-content'}">
                      {isMe ? "Anda" : m.sender_name || activeConsultation?.counselor || "Guru BK"}
                    </span>
                    <span>·</span>
                    <span>{formatDate(m.created_at)}</span>
                  </div>
                  <div
                    class="rounded-xl px-3.5 py-2 max-w-[85%] text-sm shadow-sm {isMe
                      ? 'bg-primary text-primary-content rounded-tr-none'
                      : 'bg-surface-elevated border border-border text-foreground rounded-tl-none'}"
                  >
                    <p class="whitespace-pre-wrap leading-relaxed">{m.body}</p>
                  </div>
                </div>
              {/each}
            {/if}
          </div>

          <div class="mt-3 flex items-center gap-2 border-t pt-3">
            <label class="sr-only" for="consult-msg">Pesan konsultasi</label>
            <input
              id="consult-msg"
              class="input flex-1"
              bind:value={draft}
              placeholder="Tulis pesan untuk pembimbing…"
              on:keydown={(e) => e.key === "Enter" && sendMessage()}
            />
            <button
              class="btn-primary !py-2 shrink-0 flex items-center gap-1.5"
              on:click={sendMessage}
              disabled={!draft.trim() || sendingMessage}
            >
              <Icon name="paper-plane" size="12px" />
              {sendingMessage ? "Mengirim…" : "Kirim"}
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
        <input
          class="input"
          placeholder="Topik"
          aria-label="Topik konsultasi"
          bind:value={form.topic}
        />
        <textarea
          class="input min-h-[80px]"
          placeholder="Catatan (opsional)"
          aria-label="Catatan konsultasi (opsional)"
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

<!-- Cancel confirmation modal -->
{#if confirmingCancel}
  <ConfirmDialog
    title="Batalkan Sesi Konseling"
    description={`Batalkan sesi "${confirmingCancel.topic}" dengan ${confirmingCancel.counselor}?`}
    hint="Sesi yang dibatalkan tidak bisa dikembalikan; kamu dapat mengajukan sesi baru kapan saja."
    confirmLabel="Ya, Batalkan"
    confirmRole="confirm-cancel-consultation"
    onConfirm={() => cancel(confirmingCancel!)}
    close={() => (confirmingCancel = null)}
  />
{/if}
