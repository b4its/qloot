<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Consultation, Counselor } from "$lib/types";
  import { formatDate } from "$lib/utils/format";

  let consultations: Consultation[] = [];
  let counselors: Counselor[] = [];
  let loading = true;
  let error = "";
  let form = { counselor: "", topic: "", notes: "" };
  let busy = false;

  const statusBadge: Record<string, string> = {
    pending: "badge-amber",
    completed: "badge-mint",
    cancelled: "badge-magenta",
  };

  async function load() {
    loading = true;
    try {
      consultations = await api.get<Consultation[]>("/career/consultations");
      counselors = await api.get<Counselor[]>("/career/counselors");
      if (counselors.length) form.counselor = counselors[0].name;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Failed to load consultations";
    } finally {
      loading = false;
    }
  }

  async function book() {
    busy = true;
    error = "";
    try {
      await api.post("/career/consultations", form);
      form = { ...form, topic: "", notes: "" };
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Booking failed";
    } finally {
      busy = false;
    }
  }

  async function cancel(c: Consultation) {
    await api.post(`/career/consultations/${c.id}/cancel`);
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>Counselling Room — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Konsultasi</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Counselling Room (BK)</h1>
      <p class="mt-1 text-sm muted">Jadwalkan sesi dan pantau statusnya (simulasi).</p>
    </div>
    <a href="/career" class="btn-ghost">← Career home</a>
  </div>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  <div class="mt-6 grid gap-4 lg:grid-cols-3">
    <div class="card lg:col-span-2">
      <h2 class="hud font-display text-lg font-bold">Your sessions</h2>
      {#if loading}
        <p class="mt-2 muted">Loading…</p>
      {:else if !consultations.length}
        <p class="mt-2 muted">No sessions yet. Book one on the right.</p>
      {:else}
        <ul class="mt-3 divide-y">
          {#each consultations as c}
            <li class="flex flex-wrap items-center justify-between gap-3 py-3">
              <div>
                <p class="font-medium">{c.topic}</p>
                <p class="text-xs muted">
                  {c.counselor} · {c.scheduled_at ? formatDate(c.scheduled_at) : "TBD"}
                </p>
                {#if c.notes}<p class="text-xs muted">{c.notes}</p>{/if}
              </div>
              <div class="flex items-center gap-2">
                <span class={`badge ${statusBadge[c.status] ?? "badge-neutral"}`}>{c.status}</span>
                {#if c.status === "pending"}
                  <button class="btn-ghost !py-1 text-xs" on:click={() => cancel(c)}>Cancel</button>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="card h-fit">
      <h2 class="hud font-display text-lg font-bold">Book a session</h2>
      <div class="mt-3 space-y-3">
        <select class="input" bind:value={form.counselor}>
          {#each counselors as c}<option value={c.name}>{c.name} — {c.role}</option>{/each}
        </select>
        <input class="input" placeholder="Topic" bind:value={form.topic} />
        <textarea class="input min-h-[80px]" placeholder="Notes (optional)" bind:value={form.notes}
        ></textarea>
        <button class="btn-primary w-full" on:click={book} disabled={busy || form.topic.length < 2}>
          {busy ? "Booking…" : "Request session"}
        </button>
      </div>
      <div class="mt-4 border-t pt-3">
        <p class="mono-label">Counsellors</p>
        <ul class="mt-2 space-y-2 text-sm">
          {#each counselors as c}
            <li>
              <p class="font-medium">{c.name}</p>
              <p class="text-xs muted">{c.role} · {c.focus}</p>
            </li>
          {/each}
        </ul>
      </div>
    </div>
  </div>
</div>
