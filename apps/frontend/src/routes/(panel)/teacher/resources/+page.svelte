<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { ResourceItem } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import Dialog from "$lib/components/Dialog.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let items: ResourceItem[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let category = "";
  let query = "";
  let busy = false;
  let form = { code: "", category: "course", title: "", description: "", provider: "" };
  // Deleting a resource is destructive; require an explicit confirmation.
  let deleting: ResourceItem | null = null;
  let deletingBusy = false;

  const CATEGORY_LABEL: Record<string, string> = {
    course: "Pelajaran",
    extracurricular: "Ekstrakurikuler",
    material: "Materi",
  };

  async function load() {
    loading = true;
    error = "";
    try {
      const qs = new URLSearchParams({ limit: "200" });
      if (category) qs.set("category", category);
      if (query.trim()) qs.set("q", query.trim());
      items = await api.get<ResourceItem[]>(`/career/resources?${qs.toString()}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat sumber daya";
    } finally {
      loading = false;
    }
  }

  // Debounced search so typing filters without hammering the API.
  let debounce: ReturnType<typeof setTimeout> | null = null;
  onDestroy(() => {
    if (debounce) clearTimeout(debounce);
  });

  function onSearch() {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => void load(), 250);
  }

  function resetFilters() {
    if (debounce) clearTimeout(debounce);
    query = "";
    category = "";
    void load();
  }

  // --- metrics ---------------------------------------------------------------
  $: catCounts = items.reduce<Record<string, number>>((acc, r) => {
    acc[r.category] = (acc[r.category] ?? 0) + 1;
    return acc;
  }, {});

  async function createResource() {
    busy = true;
    message = "";
    error = "";
    try {
      await api.post("/career/resources", {
        ...form,
        is_free: true,
        tags: [],
      });
      message = `Sumber daya "${form.title}" ditambahkan.`;
      form = { code: "", category: "course", title: "", description: "", provider: "" };
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menambah sumber daya";
    } finally {
      busy = false;
    }
  }

  async function removeResource(item: ResourceItem) {
    deleting = null;
    deletingBusy = true;
    try {
      await api.delete(`/career/resources/${item.code}`);
      message = "Sumber daya dihapus.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus sumber daya";
    } finally {
      deletingBusy = false;
    }
  }

  // Editing an existing catalog entry (all ResourceUpdate fields).
  let editing: {
    code: string;
    title: string;
    description: string;
    provider: string;
    is_free: boolean;
    tags: string;
  } | null = null;
  let editBusy = false;

  /** CARE-07: open the edit modal pre-filled from the row. */
  function editResource(item: ResourceItem) {
    editing = {
      code: item.code,
      title: item.title,
      description: item.description ?? "",
      provider: item.provider ?? "",
      is_free: item.is_free,
      tags: (item.tags ?? []).join(", "),
    };
  }

  async function saveEdit() {
    if (!editing) return;
    if (editing.title.trim().length < 2) {
      error = "Judul minimal 2 karakter.";
      return;
    }
    editBusy = true;
    error = "";
    message = "";
    try {
      await api.patch(`/career/resources/${editing.code}`, {
        title: editing.title.trim(),
        description: editing.description.trim() || null,
        provider: editing.provider.trim() || null,
        is_free: editing.is_free,
        tags: editing.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      });
      message = "Sumber daya diperbarui.";
      editing = null;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui sumber daya";
    } finally {
      editBusy = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Sumber Daya | Panel Guru | QLoot</title></svelte:head>

<div class="mx-auto max-w-6xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Sumber Daya"
    title="Perpustakaan Sumber Daya"
    subtitle="Kelola katalog pelajaran, ekstrakurikuler, dan materi belajar."
    backHref="/teacher"
    backLabel="Panel guru"
  />

  <PageAlerts {message} {error} />

  <!-- Metrics -->
  {#if !loading && items.length > 0}
    <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card p-4">
        <p class="mono-label text-[10px]">Total</p>
        <p class="mt-1 font-display text-3xl font-bold" data-role="total-count">{items.length}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Pelajaran</p>
        <p class="mt-1 font-display text-3xl font-bold">{catCounts["course"] ?? 0}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Ekstrakurikuler</p>
        <p class="mt-1 font-display text-3xl font-bold">{catCounts["extracurricular"] ?? 0}</p>
      </div>
      <div class="card p-4">
        <p class="mono-label text-[10px]">Materi</p>
        <p class="mt-1 font-display text-3xl font-bold">{catCounts["material"] ?? 0}</p>
      </div>
    </div>
  {/if}

  <!-- Filter + search -->
  <div class="mt-4 flex flex-wrap items-center gap-2">
    <div class="flex flex-wrap gap-1 text-xs">
      {#each [["", "Semua"], ["course", "Pelajaran"], ["extracurricular", "Ekstrakurikuler"], ["material", "Materi"]] as [val, label]}
        <button
          type="button"
          class="btn-pill !py-1 text-xs"
          class:!border-primary={category === val}
          class:!text-primary={category === val}
          on:click={() => {
            category = val;
            load();
          }}
        >
          {label}
        </button>
      {/each}
    </div>
    <div class="relative ml-auto w-full sm:w-64">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        bind:value={query}
        on:input={onSearch}
        placeholder="Cari judul atau deskripsi…"
        aria-label="Cari sumber daya"
      />
    </div>
  </div>

  <div class="card mt-6">
    <h2 class="font-display font-bold">Tambah sumber daya</h2>
    <div class="mt-3 grid gap-2 sm:grid-cols-2">
      <input
        class="input"
        placeholder="Kode (unik)"
        aria-label="Kode sumber daya (unik)"
        bind:value={form.code}
      />
      <select class="input" bind:value={form.category} aria-label="Kategori sumber daya">
        <option value="course">Pelajaran</option>
        <option value="extracurricular">Ekstrakurikuler</option>
        <option value="material">Materi</option>
      </select>
      <input
        class="input sm:col-span-2"
        placeholder="Judul"
        aria-label="Judul sumber daya"
        bind:value={form.title}
      />
      <input
        class="input"
        placeholder="Penyedia (opsional)"
        aria-label="Penyedia sumber daya"
        bind:value={form.provider}
      />
      <input
        class="input"
        placeholder="Deskripsi (opsional)"
        aria-label="Deskripsi sumber daya"
        bind:value={form.description}
      />
    </div>
    <button
      class="btn-primary mt-3 !py-1.5"
      on:click={createResource}
      disabled={busy || form.code.length < 2 || form.title.length < 2}>Tambah</button
    >
  </div>

  <div class="card mt-4 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(5) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if items.length === 0}
      {#if query.trim() || category}
        <div class="space-y-3 text-center">
          <p class="muted">Tidak ada sumber daya yang cocok dengan filtermu.</p>
          <button class="btn-ghost" on:click={resetFilters}>Reset Filter</button>
        </div>
      {:else}
        <p class="muted">Belum ada sumber daya.</p>
      {/if}
    {:else}
      <table class="w-full text-sm">
        <caption class="sr-only">Daftar sumber daya</caption>
        <thead class="text-left muted">
          <tr>
            <th class="py-1" scope="col">Kode</th>
            <th scope="col">Kategori</th>
            <th scope="col">Judul</th>
            <th class="text-right" scope="col">Aksi</th>
          </tr>
        </thead>
        <tbody>
          {#each items as r (r.code)}
            <tr class="border-t">
              <td class="py-1 font-mono text-xs">{r.code}</td>
              <td>
                <span class="badge badge-neutral">{CATEGORY_LABEL[r.category] ?? r.category}</span>
              </td>
              <td>{r.title}</td>
              <td class="text-right">
                <button
                  class="btn-icon"
                  aria-label="Ubah sumber daya"
                  on:click={() => editResource(r)}
                >
                  <Icon name="pen" size="12px" />
                </button>
                <button
                  class="btn-icon !text-tertiary"
                  aria-label="Hapus sumber daya"
                  on:click={() => (deleting = r)}
                >
                  <Icon name="trash" size="12px" />
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>

<!-- Delete confirmation modal -->
{#if deleting}
  <ConfirmDialog
    title="Hapus Sumber Daya"
    description={`Hapus sumber daya "${deleting.title}" (${deleting.code})? Tindakan ini tidak dapat dibatalkan.`}
    confirmLabel="Ya, Hapus"
    busy={deletingBusy}
    confirmRole="confirm-delete-resource"
    onConfirm={() => removeResource(deleting!)}
    close={() => (deleting = null)}
  />
{/if}

<!-- Edit modal -->
{#if editing}
  <Dialog title="Ubah Sumber Daya" size="max-w-lg" busy={editBusy} close={() => (editing = null)}>
    <div class="space-y-3">
      <label class="block">
        <span class="mono-label text-[10px]">Judul</span>
        <input class="input mt-1" bind:value={editing.title} />
      </label>
      <label class="block">
        <span class="mono-label text-[10px]">Deskripsi</span>
        <textarea class="input mt-1 min-h-[64px]" bind:value={editing.description}></textarea>
      </label>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="mono-label text-[10px]">Penyedia</span>
          <input class="input mt-1" bind:value={editing.provider} />
        </label>
        <label class="flex items-end gap-2 pb-2 text-sm">
          <input type="checkbox" bind:checked={editing.is_free} />
          <span>Gratis</span>
        </label>
      </div>
      <label class="block">
        <span class="mono-label text-[10px]">Tag (pisahkan dengan koma)</span>
        <input
          class="input mt-1"
          placeholder="mis. matematika, olimpiade"
          bind:value={editing.tags}
        />
      </label>
    </div>
    <svelte:fragment slot="footer">
      <div class="flex items-center justify-end gap-2">
        <button class="btn-ghost text-xs" on:click={() => (editing = null)}>Batal</button>
        <button class="btn-primary text-xs" on:click={saveEdit} disabled={editBusy}>
          {editBusy ? "Menyimpan…" : "Simpan"}
        </button>
      </div>
    </svelte:fragment>
  </Dialog>
{/if}
