<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Task } from "$lib/types";
  import { formatDate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";

  let tasks: Task[] = [];
  let loading = true;
  let error = "";
  let completed: Record<string, boolean> = {};
  let message = "";
  let busy = "";

  const kindIcon: Record<string, string> = {
    daily: "calendar-day",
    weekly: "calendar-week",
    learning: "book-open-reader",
    exam: "file-pen",
  };

  async function load() {
    try {
      tasks = await api.get<Task[]>("/tasks");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat tugas";
    } finally {
      loading = false;
    }
  }

  async function complete(t: Task) {
    busy = t.id;
    message = "";
    try {
      await api.post(`/tasks/${t.id}/complete`);
      completed = { ...completed, [t.id]: true };
      message = `Tugas selesai! +${t.reward_amount} OPC ditambahkan ke dompetmu.`;
    } catch (e) {
      message = e instanceof ApiError ? e.message : "Tidak dapat menyelesaikan tugas";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Tugas — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <p class="mono-label">Misi Harian</p>
  <h1 class="mt-1 font-display text-4xl font-bold">Tugas</h1>
  <p class="mt-2 muted">Selesaikan tugas untuk mengumpulkan OryphemCoin (OPC).</p>

  {#if message}
    <p class="mt-4 rounded-sm bg-primary/10 p-3 text-sm">
      <Icon name="circle-info" size="12px" class="mr-1 text-primary" />
      {message}
    </p>
  {/if}
  {#if error}
    <p class="mt-4 rounded-sm bg-tertiary/10 p-3 text-sm text-tertiary">{error}</p>
  {/if}

  {#if loading}
    <div class="mt-6 space-y-3">
      {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
    </div>
  {:else if tasks.length === 0}
    <div class="card mt-6 grid place-items-center py-16 text-center">
      <Icon name="list-check" size="28px" class="muted" />
      <p class="mt-3 font-semibold">Tidak ada tugas aktif</p>
      <p class="text-sm muted">Tugas baru akan muncul di sini.</p>
    </div>
  {:else}
    <div class="mt-6 space-y-3">
      {#each tasks as t, i}
        <div
          use:reveal={{ delay: i * 40 }}
          class="card flex flex-wrap items-center justify-between gap-4"
        >
          <div class="flex items-start gap-4">
            <span
              class="grid h-11 w-11 flex-none place-items-center rounded-xl bg-primary/10 text-primary"
            >
              <Icon name={kindIcon[t.kind] ?? "list-check"} size="17px" />
            </span>
            <div>
              <div class="flex items-center gap-2">
                <h2 class="font-semibold">{t.title}</h2>
                <span class="badge badge-neutral">{t.kind}</span>
              </div>
              <p class="text-sm muted">{t.description ?? ""}</p>
              {#if t.ends_at}<p class="text-xs muted">Berakhir {formatDate(t.ends_at)}</p>{/if}
            </div>
          </div>
          <div class="flex items-center gap-4">
            <span class="mono font-semibold text-highlight">+{t.reward_amount} OPC</span>
            {#if completed[t.id]}
              <span class="badge badge-mint"><Icon name="check" size="10px" /> Selesai</span>
            {:else}
              <button class="btn-primary" on:click={() => complete(t)} disabled={busy === t.id}>
                {#if busy === t.id}<Icon name="spinner" spin size="11px" />{:else}<Icon
                    name="check"
                    size="11px"
                  />{/if}
                Selesaikan
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
