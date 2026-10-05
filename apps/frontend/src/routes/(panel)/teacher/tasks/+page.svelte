<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Task } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { formatDate, paginate } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 10;
  const kinds = ["daily", "weekly", "learning", "exam"] as const;
  const kindLabels: Record<string, string> = {
    daily: "Harian",
    weekly: "Mingguan",
    learning: "Materi",
    exam: "Ujian",
  };
  const kindIcon: Record<string, string> = {
    daily: "calendar-day",
    weekly: "calendar-week",
    learning: "book-open-reader",
    exam: "file-pen",
  };

  let tasks: Task[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let deletingTask: Task | null = null;
  let page = 1;

  // Search & filters (server-side).
  let searchQuery = "";
  let kindFilter = "all";
  let statusFilter: "all" | "active" | "inactive" | "available" | "scheduled" | "expired" = "all";

  let newTask = {
    title: "",
    description: "",
    kind: "daily" as string,
    reward_amount: 10,
    starts_at: "",
    ends_at: "",
  };
  let editId = "";
  let editDraft = {
    title: "",
    description: "",
    reward_amount: 10,
    starts_at: "",
    ends_at: "",
  };

  /** Build the query string the role-aware `/tasks` endpoint understands. */
  function query(extra: Record<string, string | number> = {}): string {
    const params = new URLSearchParams();
    if (searchQuery.trim()) params.set("q", searchQuery.trim());
    if (kindFilter !== "all") params.set("kind", kindFilter);
    if (statusFilter !== "all") params.set("status", statusFilter);
    for (const [k, v] of Object.entries(extra)) params.set(k, String(v));
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }

  async function load() {
    loading = true;
    try {
      tasks = await api.get<Task[]>(`/tasks${query({ limit: 200 })}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat tugas";
    } finally {
      loading = false;
    }
  }

  async function applyFilters() {
    page = 1;
    await load();
  }

  function resetFilters() {
    searchQuery = "";
    kindFilter = "all";
    statusFilter = "all";
    page = 1;
    load();
  }

  /** Convert a datetime-local string to an ISO instant, or null when empty. */
  function toIso(local: string): string | null {
    if (!local) return null;
    const d = new Date(local);
    return Number.isNaN(d.getTime()) ? null : d.toISOString();
  }

  /** Convert an ISO instant to a `datetime-local` input value (local tz). */
  function toLocalInput(iso: string | null | undefined): string {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function validateWindow(starts: string, ends: string): string | null {
    const s = toIso(starts);
    const e = toIso(ends);
    if (s && e && new Date(e) <= new Date(s)) {
      return "Waktu berakhir harus setelah waktu mulai.";
    }
    return null;
  }

  async function create() {
    error = "";
    message = "";
    if (newTask.title.trim().length < 2) {
      error = "Judul tugas minimal 2 karakter.";
      return;
    }
    if (Number(newTask.reward_amount) < 0) {
      error = "Hadiah tidak boleh negatif.";
      return;
    }
    if (Number(newTask.reward_amount) > 1_000_000) {
      error = "Hadiah maksimal 1.000.000 OPT.";
      return;
    }
    if (newTask.description.trim().length > 5000) {
      error = "Deskripsi maksimal 5000 karakter.";
      return;
    }
    const windowError = validateWindow(newTask.starts_at, newTask.ends_at);
    if (windowError) {
      error = windowError;
      return;
    }
    busy = "create";
    try {
      await api.post<Task>("/tasks", {
        title: newTask.title.trim(),
        description: newTask.description.trim() || null,
        kind: newTask.kind,
        reward_amount: Number(newTask.reward_amount) || 0,
        starts_at: toIso(newTask.starts_at),
        ends_at: toIso(newTask.ends_at),
      });
      message = "Tugas dibuat.";
      newTask = {
        title: "",
        description: "",
        kind: "daily",
        reward_amount: 10,
        starts_at: "",
        ends_at: "",
      };
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
      starts_at: toLocalInput(t.starts_at),
      ends_at: toLocalInput(t.ends_at),
    };
    error = "";
    message = "";
  }

  async function saveEdit(t: Task) {
    if (editDraft.title.trim().length < 2) {
      error = "Judul tugas minimal 2 karakter.";
      return;
    }
    if (Number(editDraft.reward_amount) < 0) {
      error = "Hadiah tidak boleh negatif.";
      return;
    }
    if (Number(editDraft.reward_amount) > 1_000_000) {
      error = "Hadiah maksimal 1.000.000 OPT.";
      return;
    }
    if (editDraft.description.trim().length > 5000) {
      error = "Deskripsi maksimal 5000 karakter.";
      return;
    }
    const windowError = validateWindow(editDraft.starts_at, editDraft.ends_at);
    if (windowError) {
      error = windowError;
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
        starts_at: toIso(editDraft.starts_at),
        ends_at: toIso(editDraft.ends_at),
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
    deletingTask = t;
  }

  async function confirmRemove() {
    const t = deletingTask;
    if (!t) return;
    deletingTask = null;
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

  /** Classify a task against "now" for a status badge, mirroring the backend. */
  function statusOf(t: Task): { label: string; cls: string } {
    const now = Date.now();
    if (!t.is_active) return { label: "Nonaktif", cls: "badge-neutral" };
    if (t.starts_at && new Date(t.starts_at).getTime() > now) {
      return { label: "Terjadwal", cls: "badge-amber" };
    }
    if (t.ends_at && new Date(t.ends_at).getTime() < now) {
      return { label: "Berakhir", cls: "badge-tertiary" };
    }
    return { label: "Tersedia", cls: "badge-mint" };
  }

  // Metrics across the currently loaded (filtered) set.
  $: activeCount = tasks.filter((t) => t.is_active).length;
  $: scheduledCount = tasks.filter(
    (t) => t.is_active && t.starts_at && new Date(t.starts_at).getTime() > Date.now(),
  ).length;
  $: totalPool = tasks.reduce((sum, t) => sum + (t.reward_amount || 0), 0);

  $: totalPages = Math.max(1, Math.ceil(tasks.length / PAGE));
  $: if (page > totalPages) page = 1;
  $: pagedTasks = paginate(tasks, page, PAGE);

  onMount(load);
</script>

<svelte:head><title>Tugas | Panel Guru | QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Tugas"
    title="Tugas"
    subtitle="Buat tugas harian/mingguan, atur jadwal dan hadiah OPT untuk memotivasi siswa."
    backHref="/teacher"
    backLabel="Panel Guru"
  />

  <PageAlerts {message} {error} />

  <!-- Overview metrics -->
  {#if !loading && tasks.length > 0}
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-3">
        <span class="mono-label text-[10px]">Total Tugas</span>
        <div class="mt-1 font-display text-xl font-bold">{tasks.length}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">Aktif</span>
        <div class="mt-1 font-display text-xl font-bold text-mint">{activeCount}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">Terjadwal</span>
        <div class="mt-1 font-display text-xl font-bold text-highlight">{scheduledCount}</div>
      </div>
      <div class="card p-3">
        <span class="mono-label text-[10px]">Total Pool OPT</span>
        <div class="mt-1 font-display text-xl font-bold text-highlight">{totalPool} OPT</div>
      </div>
    </div>
  {/if}

  <!-- Create form -->
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
          {#each kinds as k}<option value={k}>{kindLabels[k]}</option>{/each}
        </select>
      </label>
      <label class="block">
        <span class="mono-label">Hadiah OPT</span>
        <input class="input mt-1" type="number" min="0" bind:value={newTask.reward_amount} />
      </label>
      <label class="block">
        <span class="mono-label">Mulai (opsional)</span>
        <input class="input mt-1" type="datetime-local" bind:value={newTask.starts_at} />
      </label>
      <label class="block">
        <span class="mono-label">Berakhir (opsional)</span>
        <input class="input mt-1" type="datetime-local" bind:value={newTask.ends_at} />
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

  <!-- Search & filter controls -->
  <div class="mt-6 flex flex-wrap items-center gap-2">
    <div class="relative w-full sm:w-60">
      <input
        type="text"
        class="input text-xs !py-1.5 w-full"
        placeholder="Cari tugas..."
        aria-label="Cari tugas"
        bind:value={searchQuery}
        on:keydown={(e) => e.key === "Enter" && applyFilters()}
      />
      {#if searchQuery}
        <button
          type="button"
          class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
          on:click={() => {
            searchQuery = "";
            applyFilters();
          }}
          aria-label="Bersihkan pencarian"
        >
          ✕
        </button>
      {/if}
    </div>

    <select class="input text-xs !py-1.5 w-auto" bind:value={kindFilter} on:change={applyFilters}>
      <option value="all">Semua jenis</option>
      {#each kinds as k}<option value={k}>{kindLabels[k]}</option>{/each}
    </select>

    <select class="input text-xs !py-1.5 w-auto" bind:value={statusFilter} on:change={applyFilters}>
      <option value="all">Semua status</option>
      <option value="available">Tersedia</option>
      <option value="scheduled">Terjadwal</option>
      <option value="expired">Berakhir</option>
      <option value="active">Aktif</option>
      <option value="inactive">Nonaktif</option>
    </select>

    {#if searchQuery || kindFilter !== "all" || statusFilter !== "all"}
      <button class="btn-ghost !py-1.5 text-xs" on:click={resetFilters}>Reset</button>
    {/if}
  </div>

  <!-- Task list -->
  <div class="mt-4 space-y-3">
    {#if loading}
      {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
    {:else if tasks.length === 0}
      <EmptyState
        icon="list-check"
        title="Belum ada tugas"
        description="Buat tugas pertama dengan formulir di atas."
      />
    {:else}
      {#each pagedTasks as t (t.id)}
        {@const st = statusOf(t)}
        <div class="card">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-start gap-3">
              <span class="tile h-10 w-10 shrink-0">
                <Icon name={kindIcon[t.kind] ?? "list-check"} size="15px" class="text-primary" />
              </span>
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <h2 class="font-display text-lg font-bold">{t.title}</h2>
                  <span class="badge badge-neutral text-[10px]">
                    {kindLabels[t.kind] ?? t.kind}
                  </span>
                  <span class="badge {st.cls} text-[10px]">{st.label}</span>
                  {#if t.honor_system}
                    <span
                      class="badge badge-amber text-[10px]"
                      title="Berbasis kejujuran (verifikasi mandiri"
                    >
                      Mandiri
                    </span>
                  {/if}
                </div>
                <p class="text-sm muted">
                  +{t.reward_amount} OPT · {t.is_active ? "aktif" : "nonaktif"}
                </p>
                {#if t.starts_at}
                  <p class="text-xs muted">Mulai {formatDate(t.starts_at)}</p>
                {/if}
                {#if t.ends_at}
                  <p class="text-xs muted">Berakhir {formatDate(t.ends_at)}</p>
                {/if}
              </div>
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
              <input
                class="input sm:col-span-2"
                placeholder="Judul"
                aria-label="Judul tugas"
                bind:value={editDraft.title}
              />
              <input
                class="input sm:col-span-2"
                placeholder="Deskripsi"
                aria-label="Deskripsi tugas"
                bind:value={editDraft.description}
              />
              <label class="block">
                <span class="mono-label text-[10px]">Hadiah OPT</span>
                <input
                  class="input mt-1"
                  type="number"
                  min="0"
                  bind:value={editDraft.reward_amount}
                />
              </label>
              <span class="hidden sm:block"></span>
              <label class="block">
                <span class="mono-label text-[10px]">Mulai</span>
                <input class="input mt-1" type="datetime-local" bind:value={editDraft.starts_at} />
              </label>
              <label class="block">
                <span class="mono-label text-[10px]">Berakhir</span>
                <input class="input mt-1" type="datetime-local" bind:value={editDraft.ends_at} />
              </label>
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
      total={tasks.length}
      {loading}
      label="tugas"
      onPrev={() => (page = Math.max(1, page - 1))}
      onNext={() => (page = Math.min(totalPages, page + 1))}
    />
  {/if}
</div>

{#if deletingTask}
  <ConfirmDialog
    title="Hapus Tugas"
    description={`Tugas "${deletingTask.title}" akan dihapus permanen.`}
    confirmLabel="Ya, Hapus"
    onConfirm={confirmRemove}
    close={() => (deletingTask = null)}
  />
{/if}
