<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import { onMount, tick } from "svelte";
  import { API_BASE, API_PREFIX, api, ApiError } from "$lib/api/client";
  import type { AssistantConversation, AssistantReply } from "$lib/types";

  interface Msg {
    role: "user" | "bot";
    text: string;
  }

  const GREETING: Msg = {
    role: "bot",
    text: "Hai! Saya **Asisten Qlo**. Tanyakan jurusan, kampus, jalur masuk (SNBP/SNBT), atau prospek karier.",
  };

  let messages: Msg[] = [GREETING];
  let input = "";
  let busy = false;
  let error = "";
  let scroller: HTMLDivElement;
  // AI credit meter (1 request = 1 ORT), refreshed from each reply.
  let ortBalance: number | null = null;
  let freeRemaining: number | null = null;
  // CARE-01: the active conversation; follow-ups are answered with context.
  let conversationId: string | null = null;
  let history: AssistantConversation[] = [];
  let historyQuery = "";
  // The search box only renders when there are more than 3 conversations; if the
  // list shrinks below that a stale query would silently filter nothing visible.
  $: if (history.length <= 3 && historyQuery) historyQuery = "";
  let copiedIndex: number | null = null;

  $: filteredHistory = history.filter((c) =>
    !historyQuery.trim() ? true : c.title.toLowerCase().includes(historyQuery.toLowerCase().trim()),
  );

  async function copyMessage(text: string, index: number) {
    copyError = "";
    if (!navigator.clipboard?.writeText) {
      copyError = "Papan klip tidak tersedia — salin pesan secara manual.";
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      copiedIndex = index;
      setTimeout(() => (copiedIndex = null), 1500);
    } catch {
      copyError = "Gagal menyalin pesan.";
    }
  }
  let copyError = "";

  const suggestions = [
    "Bedanya SNBP dan SNBT?",
    "Prospek Ilmu Komputer?",
    "Universitas terbaik untuk teknik?",
    "Rekomendasi jurusan untuk IPA?",
  ];

  function render(text: string): string {
    const escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
  }

  async function loadHistory() {
    historyError = "";
    try {
      const rows = await api.get<AssistantConversation[]>("/career/assistant/conversations");
      history = Array.isArray(rows) ? rows : [];
    } catch {
      // Distinguish a failed load from a genuinely empty history.
      history = [];
      historyError = "Gagal memuat riwayat percakapan.";
    }
  }
  let historyError = "";

  async function openConversation(id: string) {
    if (busy) return;
    try {
      const detail = await api.get<AssistantConversation>(`/career/assistant/conversations/${id}`);
      conversationId = id;
      messages = (detail.messages ?? []).map((m) => ({
        role: m.role === "user" ? "user" : "bot",
        text: m.content,
      }));
      if (messages.length === 0) messages = [GREETING];
      await scroll();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat percakapan";
    }
  }

  function newConversation() {
    conversationId = null;
    messages = [GREETING];
    error = "";
  }

  /** CARE-01: delete a saved conversation. */
  let deletingConversation: string | null = null;
  async function removeConversation(id: string) {
    deletingConversation = id;
  }

  async function confirmRemoveConversation() {
    const id = deletingConversation;
    if (!id) return;
    deletingConversation = null;
    error = "";
    try {
      await api.delete(`/career/assistant/conversations/${id}`);
      if (conversationId === id) {
        conversationId = null;
        messages = [GREETING];
      }
      await loadHistory();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus percakapan";
    }
  }

  /**
   * Stream the assistant reply via SSE (CARE-04). Falls back to the JSON
   * endpoint if the stream cannot be established.
   */
  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    input = "";
    error = "";
    messages = [...messages, { role: "user", text: q }, { role: "bot", text: "" }];
    await scroll();
    busy = true;
    const botIndex = messages.length - 1;
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}/career/assistant/stream`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          ...csrfHeader(),
        },
        body: JSON.stringify({ message: q, conversation_id: conversationId }),
      });
      if (!res.ok || !res.body) throw new Error(`stream failed (${res.status})`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let acc = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          try {
            const parsed = JSON.parse(dataLine.slice(5).trim());
            if (parsed.delta) {
              acc += parsed.delta;
              messages = messages.map((m, i) => (i === botIndex ? { ...m, text: acc } : m));
              await scroll();
            }
            if (parsed.conversation_id) conversationId = parsed.conversation_id;
          } catch {
            /* ignore malformed frame */
          }
        }
      }
      if (!acc) throw new Error("empty stream");
      await loadHistory();
    } catch {
      // JSON fallback (negotiated failure): fetch the whole answer at once.
      try {
        const reply = await api.post<AssistantReply>("/career/assistant", {
          message: q,
          conversation_id: conversationId,
        });
        messages = messages.map((m, i) => (i === botIndex ? { ...m, text: reply.answer } : m));
        if (reply.conversation_id) conversationId = reply.conversation_id;
        if (typeof reply.ort_balance === "number") ortBalance = reply.ort_balance;
        if (typeof reply.free_requests_remaining === "number")
          freeRemaining = reply.free_requests_remaining;
        await loadHistory();
      } catch (e) {
        messages = messages.slice(0, -1);
        error = e instanceof ApiError ? e.message : "Asisten tidak tersedia";
      }
    } finally {
      busy = false;
      await scroll();
    }
  }

  function csrfHeader(): Record<string, string> {
    if (typeof document === "undefined") return {};
    const m = document.cookie.match(/(?:^|;\s*)qloot_csrf=([^;]+)/);
    return m ? { "X-CSRF-Token": decodeURIComponent(m[1]) } : {};
  }

  async function scroll() {
    await tick();
    // `scrollTo` is absent in non-DOM test environments; guard it.
    scroller?.scrollTo?.({ top: scroller.scrollHeight, behavior: "smooth" });
  }

  onMount(() => {
    loadHistory();
  });
</script>

<svelte:head><title>Asisten Qlo — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Asisten</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Asisten Qlo</h1>
      <p class="mt-1 text-sm muted">
        Asisten bimbingan belajar & karier untuk pertanyaan jurusan, kampus, dan prospek karier.
      </p>
    </div>
    <div class="flex flex-col items-end gap-2">
      <div class="flex items-center gap-2">
        <button class="btn-ghost" on:click={newConversation} disabled={busy}
          >+ Percakapan baru</button
        >
        <a href="/career" class="btn-ghost">← Halaman karier</a>
      </div>
      {#if ortBalance !== null || (freeRemaining !== null && freeRemaining > 0)}
        <div class="card !py-2 !px-3 text-xs">
          <span class="mono-label">Kredit AI</span>
          <span class="ml-2 font-semibold">{ortBalance ?? 0} ORT</span>
          {#if freeRemaining}
            <span class="ml-2 muted">· {freeRemaining} gratis tersisa</span>
          {/if}
        </div>
      {/if}
    </div>
  </div>
  <p class="mt-2 text-xs muted">
    Setiap permintaan menggunakan 1 ORT. Punya saldo 0? <a
      href="/wallet"
      class="text-primary hover:underline">Tukar OPT → ORT di dompet</a
    >.
  </p>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  {#if historyError}
    <p class="alert-error mt-4 text-xs" role="alert" aria-live="assertive">
      <Icon name="triangle-exclamation" size="11px" class="inline-flex" />
      {historyError}
      <button class="btn-ghost ml-2 !py-0.5 text-xs" on:click={loadHistory}>Coba lagi</button>
    </p>
  {/if}

  {#if history.length > 0}
    <div class="mt-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <p class="mono-label">Riwayat percakapan · {history.length}</p>
        {#if history.length > 3}
          <div class="relative w-56">
            <Icon
              name="magnifying-glass"
              size="11px"
              class="absolute left-2.5 top-1/2 -translate-y-1/2 muted"
            />
            <input
              class="input text-xs !py-1 !pl-8 w-full"
              placeholder="Cari percakapan..."
              bind:value={historyQuery}
              aria-label="Cari percakapan"
            />
          </div>
        {/if}
      </div>
      <div class="mt-2 flex flex-wrap gap-2">
        {#each filteredHistory as c (c.id)}
          <span class="inline-flex items-center">
            <button
              class="btn-ghost !py-1 text-xs"
              class:!border-primary={c.id === conversationId}
              on:click={() => openConversation(c.id)}
              disabled={busy}
            >
              {c.title}
            </button>
            <button
              class="btn-icon ml-0.5 !text-tertiary"
              aria-label={`Hapus percakapan ${c.title}`}
              on:click={() => removeConversation(c.id)}
              disabled={busy}
            >
              <Icon name="trash" size="9px" />
            </button>
          </span>
        {/each}
        {#if filteredHistory.length === 0}
          <span class="text-xs muted">Tidak ada percakapan yang cocok.</span>
        {/if}
      </div>
    </div>
  {/if}

  <div class="card mt-6 flex h-[60vh] min-h-[420px] flex-col !p-0">
    <!--
      UIX-02: the transcript is a live log so screen readers announce new
      messages; the assistant text is exposed as it streams in.
    -->
    <div
      class="flex-1 space-y-3 overflow-y-auto p-5"
      bind:this={scroller}
      role="log"
      aria-live="polite"
      aria-label="Percakapan dengan Asisten Qlo"
    >
      {#each messages as m, i (i)}
        <div class="flex items-start gap-3" class:flex-row-reverse={m.role === "user"}>
          <div class="tile-neutral h-7 w-7">
            <Icon
              name={m.role === "bot" ? "robot" : "user"}
              size="13px"
              class={m.role === "bot" ? "text-primary" : ""}
            />
          </div>
          <div class="flex max-w-[80%] flex-col items-start gap-1">
            <div
              class="rounded-sm px-4 py-2 text-sm"
              class:bg-primary={m.role === "user"}
              class:text-[#05060A]={m.role === "user"}
              class:tone-ink-soft={m.role === "bot"}
              class:dark:bg-surface={m.role === "bot"}
            >
              {#if m.role === "bot" && !m.text && busy}
                <span class="inline-flex items-center gap-1" aria-label="Asisten sedang menulis">
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                </span>
              {:else}
                <!-- eslint-disable-next-line svelte/no-at-html-tags -->
                <span>{@html render(m.text)}</span>
              {/if}
            </div>
            {#if m.role === "bot" && m.text && !busy}
              <button
                type="button"
                class="text-[10px] muted hover:text-foreground"
                on:click={() => copyMessage(m.text, i)}
                aria-label="Salin jawaban"
              >
                <Icon name={copiedIndex === i ? "check" : "copy"} size="9px" />
                {copiedIndex === i ? "Tersalin" : "Salin"}
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    {#if copyError}
      <p class="px-5 pb-2 text-xs text-danger" role="alert" aria-live="assertive">{copyError}</p>
    {/if}

    <div class="border-t px-5 py-3">
      <p class="mono-label" id="suggestions-label">Pertanyaan populer</p>
      <div class="mt-2 flex flex-wrap gap-2" aria-labelledby="suggestions-label">
        {#each suggestions as s}
          <button class="btn-ghost !py-1 text-xs" on:click={() => send(s)} disabled={busy}
            >{s}</button
          >
        {/each}
      </div>
    </div>

    <div class="flex items-center gap-2 border-t p-4">
      <label class="sr-only" for="assistant-input">Pertanyaan untuk Asisten Qlo</label>
      <input
        id="assistant-input"
        class="input"
        placeholder="Tanyakan jurusan, kampus, atau karier…"
        bind:value={input}
        on:keydown={(e) => e.key === "Enter" && send()}
        disabled={busy}
      />
      <button class="btn-primary" on:click={() => send()} disabled={busy || !input.trim()}
        >Kirim</button
      >
    </div>
  </div>
</div>

{#if deletingConversation}
  <ConfirmDialog
    title="Hapus Percakapan"
    description="Percakapan ini akan dihapus dari riwayat Asisten Qlo."
    confirmLabel="Ya, Hapus"
    onConfirm={confirmRemoveConversation}
    close={() => (deletingConversation = null)}
  />
{/if}
