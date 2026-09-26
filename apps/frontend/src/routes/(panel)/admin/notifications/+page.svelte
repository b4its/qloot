<script lang="ts">
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import { auth, hasRole } from "$lib/stores/auth";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  let title = "";
  let body = "";
  let kind = "system";
  let targetMode: "all" | "specific" = "all";
  let specificUserIds = "";

  let sending = false;
  let error = "";
  let message = "";

  async function sendBroadcast() {
    if (!title.trim()) {
      error = "Judul notifikasi tidak boleh kosong";
      return;
    }

    let user_ids: string[] | null = null;
    if (targetMode === "specific") {
      const parsed = specificUserIds
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter(Boolean);
      if (parsed.length === 0) {
        error = "Tentukan minimal satu ID pengguna jika memilih mode spesifik";
        return;
      }
      user_ids = parsed;
    }

    sending = true;
    error = "";
    message = "";

    try {
      const res = await api.post<{ message: string }>("/admin/notifications", {
        title: title.trim(),
        body: body.trim() || null,
        kind,
        user_ids,
      });
      message = res.message || "Siaran notifikasi berhasil dikirim.";
      title = "";
      body = "";
      specificUserIds = "";
      targetMode = "all";
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengirim siaran notifikasi";
    } finally {
      sending = false;
    }
  }
</script>

<svelte:head><title>Siaran Notifikasi — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Komunikasi"
    title="Siaran Notifikasi"
    subtitle="Kirim pengumuman atau notifikasi sistem secara massal ke seluruh pengguna aktif atau penerima spesifik."
    backHref="/admin"
    backLabel="Admin"
  />

  <PageAlerts {message} {error} />

  <form on:submit|preventDefault={sendBroadcast} class="card mt-6 space-y-6">
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
          <span>Semua Pengguna Aktif</span>
        </label>
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="radio"
            name="targetMode"
            value="specific"
            bind:group={targetMode}
            disabled={sending}
          />
          <span>Pengguna Spesifik (UUID)</span>
        </label>
      </div>
    </div>

    {#if targetMode === "specific"}
      <div>
        <label for="target-uuids" class="mono-label block mb-1"
          >Daftar UUID Pengguna (pisahkan dengan koma atau baris baru)</label
        >
        <textarea
          id="target-uuids"
          class="input font-mono text-xs w-full min-h-[90px]"
          placeholder="uuid-1, uuid-2&#10;uuid-3"
          bind:value={specificUserIds}
          disabled={sending}
        ></textarea>
      </div>
    {/if}

    <div class="pt-2 flex justify-end">
      <button type="submit" class="btn-primary" disabled={sending}>
        {sending ? "Mengirim Siaran…" : "Kirim Siaran Notifikasi"}
      </button>
    </div>
  </form>
</div>
