<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, apiGetPaged, ApiError } from "$lib/api/client";
  import type { User } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  let title = "";
  let body = "";
  let kind = "system";
  let targetMode: "all" | "specific" = "all";
  // Selected recipients for specific mode (a real picker, not raw UUID paste).
  let selected = new Map<string, User>();

  let sending = false;
  let error = "";
  let message = "";
  let confirming = false;

  // Recipient count for the "all users" mode.
  let activeUsers: number | null = null;
  let activeUsersError = false;
  onMount(() => {
    (async () => {
      try {
        const res = await apiGetPaged<User[]>("/admin/users?is_active=true&limit=1");
        activeUsers = res.total ?? res.data.length;
      } catch {
        activeUsers = null;
        activeUsersError = true;
      }
    })().catch(() => {
      activeUsers = null;
      activeUsersError = true;
    });
  });

  // --- recipient picker ------------------------------------------------------
  let userQuery = "";
  let userResults: User[] = [];
  let searching = false;
  let searchError = "";
  let searchDebounce: ReturnType<typeof setTimeout> | null = null;

  function searchUsers() {
    if (searchDebounce) clearTimeout(searchDebounce);
    searchDebounce = setTimeout(async () => {
      const q = userQuery.trim();
      searchError = "";
      if (q.length < 2) {
        userResults = [];
        return;
      }
      searching = true;
      try {
        userResults = await api.get<User[]>(`/admin/users?q=${encodeURIComponent(q)}&limit=8`);
      } catch {
        userResults = [];
        searchError = "Pencarian penerima gagal. Coba lagi.";
      } finally {
        searching = false;
      }
    }, 250);
  }

  function addRecipient(u: User) {
    selected.set(u.id, u);
    selected = new Map(selected);
    userResults = [];
    userQuery = "";
  }
  function removeRecipient(id: string) {
    selected.delete(id);
    selected = new Map(selected);
  }

  // --- validation + preview --------------------------------------------------
  $: recipientCount = targetMode === "all" ? activeUsers : selected.size;
  $: canSubmit =
    title.trim().length >= 1 && !sending && (targetMode === "all" || selected.size > 0);

  const KIND_LABEL: Record<string, string> = {
    system: "Sistem",
    info: "Informasi",
    quest: "Quest",
    achievement: "Pencapaian",
  };
  const KIND_ICON: Record<string, string> = {
    system: "bell",
    info: "circle-info",
    quest: "trophy",
    achievement: "medal",
  };

  async function sendBroadcast() {
    if (!title.trim()) {
      error = "Judul notifikasi tidak boleh kosong";
      return;
    }
    if (targetMode === "specific" && selected.size === 0) {
      error = "Tentukan minimal satu penerima.";
      return;
    }
    sending = true;
    error = "";
    message = "";
    confirming = false;
    try {
      const user_ids = targetMode === "specific" ? [...selected.keys()] : null;
      const res = await api.post<{ message: string }>("/admin/notifications", {
        title: title.trim(),
        body: body.trim() || null,
        kind,
        user_ids,
      });
      message = res.message || "Siaran notifikasi berhasil dikirim.";
      title = "";
      body = "";
      selected = new Map();
      targetMode = "all";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim siaran notifikasi";
    } finally {
      sending = false;
    }
  }
</script>

<svelte:head><title>Siaran Notifikasi | Admin | QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Komunikasi"
    title="Siaran Notifikasi"
    subtitle="Kirim pengumuman atau notifikasi sistem secara massal ke seluruh pengguna aktif atau penerima spesifik."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  <div class="mt-6 grid gap-4 lg:grid-cols-[1fr_320px]">
    <form
      on:submit|preventDefault={() => (confirming = true)}
      class="card space-y-6"
      aria-label="Form siaran"
    >
      <div>
        <label for="broadcast-title" class="mono-label block mb-1">Judul Notifikasi *</label>
        <input
          id="broadcast-title"
          type="text"
          class="input w-full"
          placeholder="Contoh: Pemeliharaan Sistem / Quest Baru Tersedia"
          bind:value={title}
          required
          disabled={sending}
          aria-invalid={title.length > 0 && title.trim().length === 0}
        />
      </div>

      <div>
        <label for="broadcast-kind" class="mono-label block mb-1">Jenis Notifikasi</label>
        <select
          id="broadcast-kind"
          class="input w-full sm:w-auto"
          bind:value={kind}
          disabled={sending}
        >
          <option value="system">Sistem (System)</option>
          <option value="info">Informasi (Info)</option>
          <option value="quest">Quest (Tantangan)</option>
          <option value="achievement">Pencapaian (Achievement)</option>
        </select>
      </div>

      <div>
        <label for="broadcast-body" class="mono-label block mb-1">Isi Pesan (Opsional)</label>
        <textarea
          id="broadcast-body"
          class="input w-full min-h-[120px]"
          placeholder="Tuliskan detail pengumuman yang akan dibaca pengguna pada panel notifikasi..."
          bind:value={body}
          disabled={sending}
        ></textarea>
      </div>

      <div>
        <span class="mono-label block mb-2">Target Pengguna</span>
        <div class="flex flex-col gap-2 sm:flex-row sm:gap-6">
          <label class="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="radio"
              name="targetMode"
              value="all"
              bind:group={targetMode}
              disabled={sending}
            />
            <span
              >Semua Pengguna Aktif {#if activeUsers !== null}<span class="muted"
                  >({formatNumber(activeUsers)})</span
                >{:else if activeUsersError}<span class="muted">(jumlah tidak diketahui)</span
                >{/if}</span
            >
          </label>
          <label class="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="radio"
              name="targetMode"
              value="specific"
              bind:group={targetMode}
              disabled={sending}
            />
            <span>Penerima Spesifik</span>
          </label>
        </div>
      </div>

      {#if targetMode === "specific"}
        <div>
          <label for="user-search" class="mono-label block mb-1"
            >Cari penerima (nama atau email)</label
          >
          <div class="relative">
            <Icon
              name="magnifying-glass"
              size="12px"
              class="absolute left-3 top-1/2 -translate-y-1/2 muted"
            />
            <input
              id="user-search"
              class="input !pl-8 w-full"
              placeholder="Ketik minimal 2 huruf…"
              bind:value={userQuery}
              on:input={searchUsers}
              disabled={sending}
            />
          </div>
          {#if searching}
            <p class="mt-1 text-xs muted" role="status" aria-live="polite">Mencari…</p>
          {:else if searchError}
            <p class="mt-1 text-xs text-danger" role="alert" aria-live="assertive">{searchError}</p>
          {:else if userResults.length > 0}
            <ul class="mt-1 card !p-0 divide-y max-h-56 overflow-y-auto">
              {#each userResults as u (u.id)}
                <li>
                  <button
                    type="button"
                    class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-ink/5"
                    on:click={() => addRecipient(u)}
                  >
                    <span>
                      <span class="font-medium">{u.full_name}</span>
                      <span class="block text-xs muted">{u.email}</span>
                    </span>
                    <Icon name="plus" size="11px" class="text-primary" />
                  </button>
                </li>
              {/each}
            </ul>
          {/if}

          {#if selected.size > 0}
            <div class="mt-2 flex flex-wrap gap-1.5">
              {#each [...selected.values()] as u (u.id)}
                <span class="badge badge-indigo">
                  {u.full_name}
                  <button
                    type="button"
                    class="ml-1 hover:text-danger"
                    on:click={() => removeRecipient(u.id)}
                    aria-label={`Hapus ${u.full_name}`}
                  >
                    <Icon name="xmark" size="9px" />
                  </button>
                </span>
              {/each}
            </div>
          {/if}
        </div>
      {/if}

      <div class="pt-2 flex items-center justify-between gap-2 border-t">
        <span class="mono-label text-[10px]">
          {recipientCount === null
            ? "Penerima aktif: -"
            : `Perkiraan penerima: ${formatNumber(recipientCount)}`}
        </span>
        <button type="submit" class="btn-primary" disabled={!canSubmit}>
          {sending ? "Mengirim Siaran…" : "Kirim Siaran Notifikasi"}
        </button>
      </div>
    </form>

    <!-- Live preview -->
    <aside class="card h-fit lg:sticky lg:top-28">
      <p class="mono-label">Pratinjau notifikasi</p>
      <div class="mt-3 flex items-start gap-3 rounded-sm border p-3">
        <span class="tile-neutral h-9 w-9 flex-none">
          <Icon name={KIND_ICON[kind] ?? "bell"} size="14px" class="text-primary" />
        </span>
        <div class="min-w-0">
          <p class="flex items-center justify-between gap-2">
            <span class="font-medium {title.trim() ? '' : 'muted'}"
              >{title.trim() || "Judul notifikasi"}</span
            >
            <span class="text-[10px] muted">baru saja</span>
          </p>
          {#if body.trim()}<span class="mt-0.5 block text-sm muted">{body}</span>{/if}
          <span class="mt-1 inline-block badge badge-neutral text-[10px]"
            >{KIND_LABEL[kind] ?? kind}</span
          >
        </div>
      </div>
      <p class="mt-3 text-xs muted">
        {#if targetMode === "all"}
          Dikirim ke seluruh pengguna aktif.
        {:else}
          Dikirim ke {selected.size} penerima terpilih.
        {/if}
      </p>
    </aside>
  </div>
</div>

<!-- Send confirmation modal -->
{#if confirming}
  <ConfirmDialog
    title="Kirim Siaran Notifikasi"
    description={targetMode === "all"
      ? `Kirim "${title}" ke seluruh pengguna aktif${activeUsers !== null ? ` (${formatNumber(activeUsers)})` : ""}?`
      : `Kirim "${title}" ke ${selected.size} penerima terpilih?`}
    hint="Notifikasi langsung tersimpan di feed penerima. Tindakan ini tercatat."
    confirmLabel="Ya, Kirim"
    confirmRole="confirm-broadcast"
    tone="primary"
    busy={sending}
    onConfirm={sendBroadcast}
    close={() => (confirming = false)}
  />
{/if}
