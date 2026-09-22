<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Task } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { formatDate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let tasks: Task[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let page = 1;
  let hasMore = false;

  const kinds = ["daily", "weekly", "learning", "exam"];
  let newTask = { title: "", description: "", kind: "daily", reward_amount: 10 };
  let editId = "";
  let editDraft = { title: "", description: "", reward_amount: 10 };

  async function load() {
    loading = true;
    try {
      tasks = await api.get<Task[]>(`/tasks?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = tasks.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat tugas";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    page = next;
    load();
  }

  async function create() {
    error = "";
    message = "";
    busy = "create";
    try {
      await api.post<Task>("/tasks", {
        title: newTask.title.trim(),
        description: newTask.description.trim() || null,
        kind: newTask.kind,
        reward_amount: Number(newTask.reward_amount) || 0,
      });
      message = "Tugas dibuat.";
      newTask = { title: "", description: "", kind: "daily", reward_amount: 10 };
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat tugas";
    } finally {
      busy = "";
    }
  }

  function startEdit(t: Task) {
    editId = t.id;
    editDraft = {
      title: t.title,
      description: t.description ?? "",
      reward_amount: t.reward_amount,
    };
    error = "";
    message = "";
  }

  async function saveEdit(t: Task) {
    if (editDraft.title.trim().length < 2) {
      error = "Judul tugas minimal 2 karakter.";
      return;
    }
    error = "";
    message = "";
    busy = `e-${t.id}`;
    try {
      await api.patch<Task>(`/tasks/${t.id}`, {
        title: editDraft.title.trim(),
        description: editDraft.description.trim() || null,
        reward_amount: Number(editDraft.reward_amount) || 0,
      });
      message = "Tugas diperbarui.";
      editId = "";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui tugas";
    } finally {
      busy = "";
    }
  }

  async function toggleActive(t: Task) {
    error = "";
    message = "";
    busy = `p-${t.id}`;
    try {
      await api.patch<Task>(`/tasks/${t.id}`, { is_active: !t.is_active });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah status tugas";
    } finally {
      busy = "";
    }
  }

  async function remove(t: Task) {
    if (!confirm(`Hapus tugas "${t.title}"?`)) return;
    error = "";
    message = "";
    busy = `d-${t.id}`;
    try {
      await api.delete(`/tasks/${t.id}`);
      message = "Tugas dihapus.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus tugas";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Tugas — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Tugas"
    title="Tugas"
    subtitle="Buat tugas harian/mingguan untuk memotivasi siswa mengumpulkan OPT."
    backHref="/teacher"
    backLabel="Panel Guru"
  />

  <PageAlerts {message} {error} />

  <div class="card mt-6">
    <h2 class="hud font-display text-lg font-bold">Tugas baru</h2>
    <div class="mt-3 grid gap-3 sm:grid-cols-2">
      <label class="block sm:col-span-2">
        <span class="mono-label">Judul</span>
        <input class="input mt-1" placeholder="mis. Baca materi Bab 1" bind:value={newTask.title} />
      </label>
      <label class="block sm:col-span-2">
        <span class="mono-label">Deskripsi</span>
        <input class="input mt-1" placeholder="Opsional" bind:value={newTask.description} />
      </label>
      <label class="block">
        <span class="mono-label">Jenis</span>
        <select class="input mt-1" bind:value={newTask.kind}>
          {#each kinds as k}<option value={k}>{k}</option>{/each}
        </select>
      </label>
      <label class="block">
        <span class="mono-label">Hadiah OPT</span>
        <input class="input mt-1" type="number" min="0" bind:value={newTask.reward_amount} />
      </label>
    </div>
    <button
      class="btn-primary mt-3"
      on:click={create}
      disabled={newTask.title.length < 2 || busy === "create"}
    >
      {busy === "create" ? "Membuat…" : "Buat tugas"}
    </button>
  </div>

  <div class="mt-6 space-y-3">
    {#if loading}
      {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
    {:else if tasks.length === 0}
      <div class="card grid place-items-center py-12 text-center">
        <Icon name="list-check" size="26px" class="muted" />
        <p class="mt-3 font-semibold">Belum ada tugas</p>
        <p class="text-sm muted">Buat tugas pertama dengan formulir di atas.</p>
      </div>
    {:else}
      {#each tasks as t}
        <div class="card">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 class="font-display text-lg font-bold">{t.title}</h2>
              <p class="text-sm muted">
                {t.kind} · +{t.reward_amount} OPT · {t.is_active ? "aktif" : "nonaktif"}
              </p>
              {#if t.ends_at}<p class="text-xs muted">Berakhir {formatDate(t.ends_at)}</p>{/if}
            </div>
            <div class="flex items-center gap-2">
              {#if editId !== t.id}
                <button
                  class="btn-secondary"
                  on:click={() => toggleActive(t)}
                  disabled={busy === `p-${t.id}`}
                >
                  {t.is_active ? "Nonaktifkan" : "Aktifkan"}
                </button>
                <button
                  class="btn-ghost"
                  on:click={() => startEdit(t)}
                  disabled={busy === `e-${t.id}`}
                >
                  <Icon name="pen" size="11px" /> Ubah
                </button>
              {/if}
              <button
                class="btn-icon !text-tertiary hover:!border-tertiary"
                on:click={() => remove(t)}
                disabled={busy === `d-${t.id}`}
                aria-label="Hapus tugas"
              >
                <Icon name="trash" size="12px" />
              </button>
            </div>
          </div>
          {#if editId === t.id}
            <div class="mt-3 grid gap-3 border-t pt-3 sm:grid-cols-2">
              <input class="input sm:col-span-2" placeholder="Judul" bind:value={editDraft.title} />
              <input
                class="input sm:col-span-2"
                placeholder="Deskripsi"
                bind:value={editDraft.description}
              />
              <input class="input" type="number" min="0" bind:value={editDraft.reward_amount} />
            </div>
            <div class="mt-3 flex gap-2">
              <button
                class="btn-primary"
                on:click={() => saveEdit(t)}
                disabled={editDraft.title.length < 2 || busy === `e-${t.id}`}
              >
                {busy === `e-${t.id}` ? "Menyimpan…" : "Simpan perubahan"}
              </button>
              <button class="btn-ghost" on:click={() => (editId = "")}>Batal</button>
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </div>

  {#if !loading && tasks.length > 0}
    <Pagination
      {page}
      pageSize={PAGE}
      {hasMore}
      {loading}
      label="tugas"
      onPrev={() => go(-1)}
      onNext={() => go(1)}
    />
  {/if}
</div>
