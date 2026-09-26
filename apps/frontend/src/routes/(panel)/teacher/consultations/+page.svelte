<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Consultation, ConsultationMessage } from "$lib/types";
  import { formatDate, statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Icon from "$lib/components/Icon.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let consultations: Consultation[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let statusFilter = "";
  let openId = "";
  let thread: ConsultationMessage[] = [];
  let draft = "";

  const statusBadge: Record<string, string> = {
    pending: "badge-amber",
    accepted: "badge-indigo",
    completed: "badge-mint",
    cancelled: "badge-magenta",
  };

  $: activeConsultation = consultations.find((x) => x.id === openId);

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
    if (c.scheduled_at) {
      try {
        const d = new Date(c.scheduled_at);
        rescheduleInput = d.toISOString().slice(0, 16);
      } catch {
        rescheduleInput = "";
      }
    } else {
      rescheduleInput = "";
    }
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

  async function reschedule(c: Consultation) {
    openReschedule(c);
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

  <div class="mt-6 flex flex-wrap items-end gap-3">
    <label class="flex flex-col text-xs">
      <span class="muted mb-1">Status</span>
      <select class="input !w-auto" bind:value={statusFilter} on:change={load}>
        <option value="">Semua</option>
        <option value="pending">Menunggu</option>
        <option value="accepted">Diterima</option>
        <option value="completed">Selesai</option>
        <option value="cancelled">Dibatalkan</option>
      </select>
    </label>
    <button class="btn-ghost !py-1.5" on:click={load} disabled={loading}>Muat ulang</button>
  </div>

  <div class="card mt-6">
    {#if loading}
      <div class="space-y-2">
        {#each Array(4) as _}<div class="skeleton h-10"></div>{/each}
      </div>
    {:else if consultations.length === 0}
      <p class="muted">Belum ada konsultasi.</p>
    {:else}
      <ul class="divide-y">
        {#each consultations as c (c.id)}
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

        <div class="mt-3 max-h-80 space-y-3 overflow-y-auto px-1 py-2">
          {#if thread.length === 0}
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
            disabled={!draft.trim()}
          >
            <Icon name="paper-plane" size="12px" /> Kirim
          </button>
        </div>
      </div>
    {/if}
  </div>

  {#if rescheduleTarget}
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
    >
      <div class="card w-full max-w-md shadow-2xl space-y-4">
        <div class="flex items-center justify-between border-b pb-3">
          <h3 class="font-bold text-base">Jadwalkan Ulang Konsultasi</h3>
          <button class="btn-ghost !p-1 text-xs" on:click={() => (rescheduleTarget = null)}>
            <Icon name="xmark" size="12px" />
          </button>
        </div>
        <p class="text-xs muted">
          Tentukan waktu sesi baru untuk <strong>{rescheduleTarget.topic}</strong>
          {#if rescheduleTarget.student_name}bersama siswa <strong
              >{rescheduleTarget.student_name}</strong
            >{/if}.
        </p>
        <label class="flex flex-col gap-1 text-xs">
          <span class="mono-label">Waktu Sesi Baru</span>
          <input type="datetime-local" class="input text-sm" bind:value={rescheduleInput} />
        </label>
        <div class="flex items-center justify-end gap-2 pt-2">
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
      </div>
    </div>
  {/if}
</div>
