<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Consultation, ConsultationMessage } from "$lib/types";
  import { formatDate, statusLabel, toLocalInput } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import Dialog from "$lib/components/Dialog.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let consultations: Consultation[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let statusFilter = "";
  let query = "";
  let openId = "";
  let thread: ConsultationMessage[] = [];
  let threadLoading = false;
  let draft = "";
  let sendingMessage = false;

  const statusBadge: Record<string, string> = {
    pending: "badge-amber",
    accepted: "badge-indigo",
    completed: "badge-mint",
    cancelled: "badge-magenta",
  };

  const STATUS_TABS: { value: string; label: string }[] = [
    { value: "", label: "Semua" },
    { value: "pending", label: "Menunggu" },
    { value: "accepted", label: "Diterima" },
    { value: "completed", label: "Selesai" },
    { value: "cancelled", label: "Dibatalkan" },
  ];

  $: activeConsultation = consultations.find((x) => x.id === openId);

  // --- metrics + client-side search (over the fetched set) -------------------
  $: pendingCount = consultations.filter((c) => c.status === "pending").length;
  $: acceptedCount = consultations.filter((c) => c.status === "accepted").length;
  $: completedCount = consultations.filter((c) => c.status === "completed").length;

  $: filtered = consultations.filter((c) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase().trim();
    return c.topic.toLowerCase().includes(q) || (c.student_name ?? "").toLowerCase().includes(q);
  });

  function setStatus(value: string) {
    statusFilter = value;
    void load();
  }

  let rescheduleTarget: Consultation | null = null;
  let rescheduleInput = "";

  async function load() {
    loading = true;
    error = "";
    try {
      const qs = statusFilter ? `?status=${statusFilter}` : "";
      consultations = await api.get<Consultation[]>(`/career/consultations/managed${qs}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat konsultasi";
    } finally {
      loading = false;
    }
  }

  async function act(c: Consultation, action: "accept" | "complete") {
    busy = c.id;
    message = "";
    try {
      await api.post(`/career/consultations/${c.id}/${action}`);
      message = `Konsultasi ${action === "accept" ? "diterima" : "diselesaikan"}.`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui konsultasi";
    } finally {
      busy = "";
    }
  }

  function openReschedule(c: Consultation) {
    rescheduleTarget = c;
    rescheduleInput = toLocalInput(c.scheduled_at);
  }

  /** CARE-06: reschedule a consultation to a new slot (ISO datetime). */
  async function confirmReschedule() {
    if (!rescheduleTarget || !rescheduleInput) return;
    const c = rescheduleTarget;
    error = "";
    message = "";
    busy = c.id;
    try {
      await api.post(`/career/consultations/${c.id}/reschedule`, {
        scheduled_at: new Date(rescheduleInput).toISOString(),
      });
      message = "Konsultasi dijadwalkan ulang.";
      rescheduleTarget = null;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menjadwalkan ulang";
    } finally {
      busy = "";
    }
  }

  async function openThread(c: Consultation) {
    openId = c.id;
    threadLoading = true;
    // Clear the previous thread so a stale conversation never flashes while the
    // new one loads.
    thread = [];
    try {
      thread = await api.get<ConsultationMessage[]>(`/career/consultations/${c.id}/messages`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pesan";
    } finally {
      threadLoading = false;
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

<svelte:head><title>Konsultasi BK — QLoot</title></svelte:head>

<div class="mx-auto max-w-6xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · BK"
    title="Konsultasi BK"
    subtitle="Terima permintaan konsultasi siswa, jadwalkan ulang, dan balas pesannya."
    backHref="/teacher"
    backLabel="Panel guru"
  />

  <PageAlerts {message} {error} />

  <!-- Metrics -->
  {#if !loading && consultations.length > 0}
    <div class="mt-6 grid grid-cols-3 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total</p>
        <p class="mt-1 font-display text-3xl font-bold" data-role="total-count">
          {consultations.length}
        </p>
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
  {/if}

  <!-- Status tabs + search -->
  <div class="mt-4 flex flex-wrap items-center gap-2">
    <div
      class="flex flex-wrap gap-1 rounded-sm border p-1 w-fit"
      role="tablist"
      aria-label="Status"
    >
      {#each STATUS_TABS as t (t.value)}
        <button
          role="tab"
          aria-selected={statusFilter === t.value}
          class="btn-ghost !px-3 !py-1.5 text-xs"
          class:bg-primary={statusFilter === t.value}
          class:!text-[#05060A]={statusFilter === t.value}
          on:click={() => setStatus(t.value)}
        >
          {t.label}
        </button>
      {/each}
    </div>
    <div class="relative w-full sm:w-64">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        placeholder="Cari topik atau nama siswa..."
        bind:value={query}
        aria-label="Cari konsultasi"
      />
    </div>
  </div>

  <div class="card mt-6">
    {#if loading}
      <div class="space-y-2">
        {#each Array(4) as _}<div class="skeleton h-10"></div>{/each}
      </div>
    {:else if consultations.length === 0}
      <p class="muted">Belum ada konsultasi.</p>
    {:else if filtered.length === 0}
      <div class="grid place-items-center py-12 text-center">
        <p class="muted text-sm">Tidak ada konsultasi yang cocok dengan pencarianmu.</p>
        <button class="btn-ghost mt-3 !py-1 text-xs" on:click={() => (query = "")}>
          Reset Pencarian
        </button>
      </div>
    {:else}
      <ul class="divide-y">
        {#each filtered as c (c.id)}
          <li
            class="flex flex-wrap items-center justify-between gap-3 py-3 rounded-lg hover:bg-surface-elevated/30 px-2 transition-colors"
          >
            <div>
              <div class="flex items-center gap-2">
                <p class="font-semibold text-sm">{c.topic}</p>
                {#if c.student_name}
                  <span class="badge badge-indigo text-[10px]">
                    Siswa: {c.student_name}
                  </span>
                {/if}
              </div>
              <p class="text-xs muted mt-0.5 flex items-center gap-2">
                <span>{c.counselor}</span>
                <span>·</span>
                <span class="inline-flex items-center gap-1">
                  <Icon name="calendar" size="10px" />
                  {c.scheduled_at ? formatDate(c.scheduled_at) : "belum ada jadwal"}
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
                  class="btn-primary !py-1 text-xs"
                  on:click={() => act(c, "accept")}
                  disabled={busy === c.id}>Terima</button
                >
              {/if}
              {#if c.status === "accepted"}
                <button
                  class="btn-primary !py-1 text-xs"
                  on:click={() => act(c, "complete")}
                  disabled={busy === c.id}>Selesaikan</button
                >
              {/if}
              {#if c.status === "pending" || c.status === "accepted"}
                <button
                  class="btn-ghost !py-1 text-xs"
                  on:click={() => openReschedule(c)}
                  disabled={busy === c.id}>Jadwalkan ulang</button
                >
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {/if}

    {#if openId}
      <div class="mt-4 border-t pt-4">
        <div class="flex items-center justify-between pb-3 border-b">
          <div>
            <p class="mono-label text-primary">Utas Konsultasi</p>
            <h3 class="font-bold text-sm">
              {activeConsultation?.topic || "Konsultasi"}
              {#if activeConsultation?.student_name}
                <span class="text-xs muted font-normal ml-1"
                  >· Siswa: {activeConsultation.student_name}</span
                >
              {/if}
            </h3>
          </div>
          <button class="btn-ghost !py-1 text-xs" on:click={() => (openId = "")}>
            <Icon name="xmark" size="11px" /> Tutup
          </button>
        </div>

        <div
          class="mt-3 max-h-80 space-y-3 overflow-y-auto px-1 py-2"
          role="log"
          aria-live="polite"
        >
          {#if threadLoading}
            <div class="space-y-2">
              {#each Array(3) as _}<div class="skeleton h-12"></div>{/each}
            </div>
          {:else if thread.length === 0}
            <div class="text-center py-8">
              <p class="text-xs muted">
                Belum ada pesan. Mulai percakapan dengan siswa di bawah ini.
              </p>
            </div>
          {:else}
            {#each thread as m (m.id)}
              {@const isMe = m.sender_id === $auth.user?.id}
              <div class="flex flex-col {isMe ? 'items-end' : 'items-start'}">
                <div class="flex items-center gap-1.5 mb-0.5 text-[11px] muted">
                  <span class="font-semibold {isMe ? 'text-primary' : 'text-neutral-content'}">
                    {isMe ? "Anda (Guru)" : m.sender_name || "Siswa"}
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
          <label class="sr-only" for="bk-msg">Balasan konsultasi</label>
          <input
            id="bk-msg"
            class="input flex-1"
            bind:value={draft}
            placeholder="Tulis balasan untuk siswa…"
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

  {#if rescheduleTarget}
    <Dialog
      title="Jadwalkan Ulang Konsultasi"
      description={`Tentukan waktu sesi baru untuk ${rescheduleTarget.topic}${rescheduleTarget.student_name ? ` bersama siswa ${rescheduleTarget.student_name}` : ""}.`}
      size="max-w-md"
      busy={busy === rescheduleTarget.id}
      close={() => (rescheduleTarget = null)}
    >
      <label class="flex flex-col gap-1 text-xs">
        <span class="mono-label">Waktu Sesi Baru</span>
        <input
          type="datetime-local"
          class="input text-sm"
          bind:value={rescheduleInput}
          data-autofocus
        />
      </label>
      <svelte:fragment slot="footer">
        <div class="flex items-center justify-end gap-2">
          <button class="btn-ghost text-xs" on:click={() => (rescheduleTarget = null)}>Batal</button
          >
          <button
            class="btn-primary text-xs"
            disabled={!rescheduleInput || busy === rescheduleTarget.id}
            on:click={confirmReschedule}
          >
            {busy === rescheduleTarget.id ? "Menyimpan…" : "Simpan Jadwal"}
          </button>
        </div>
      </svelte:fragment>
    </Dialog>
  {/if}
</div>
