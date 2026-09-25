<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Consultation, ConsultationMessage } from "$lib/types";
  import { formatDate, statusLabel } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

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

  /** CARE-06: reschedule a consultation to a new slot (ISO datetime). */
  async function reschedule(c: Consultation) {
    const when = prompt("Jadwal baru (YYYY-MM-DDTHH:MM)", c.scheduled_at ?? "");
    if (!when) return;
    error = "";
    message = "";
    busy = c.id;
    try {
      await api.post(`/career/consultations/${c.id}/reschedule`, {
        scheduled_at: new Date(when).toISOString(),
      });
      message = "Konsultasi dijadwalkan ulang.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menjadwalkan ulang";
    } finally {
      busy = "";
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
          <li class="flex flex-wrap items-center justify-between gap-3 py-3">
            <div>
              <p class="font-medium">{c.topic}</p>
              <p class="text-xs muted">
                {c.counselor} · {c.scheduled_at ? formatDate(c.scheduled_at) : "belum ada jadwal"}
              </p>
              {#if c.notes}<p class="text-xs muted">{c.notes}</p>{/if}
            </div>
            <div class="flex items-center gap-2">
              <span class="badge badge-neutral">{statusLabel(c.status)}</span>
              <button class="btn-ghost !py-1 text-xs" on:click={() => openThread(c)}>Pesan</button>
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
                  on:click={() => reschedule(c)}
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
          <label class="sr-only" for="bk-msg">Balasan konsultasi</label>
          <input
            id="bk-msg"
            class="input"
            bind:value={draft}
            placeholder="Tulis balasan…"
            on:keydown={(e) => e.key === "Enter" && sendMessage()}
          />
          <button class="btn-primary !py-1.5" on:click={sendMessage} disabled={!draft.trim()}>
            Kirim
          </button>
        </div>
      </div>
    {/if}
  </div>
</div>
