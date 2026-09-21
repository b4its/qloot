<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { onMount, tick } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { AssistantReply } from "$lib/types";

  interface Msg {
    role: "user" | "bot";
    text: string;
    typing?: boolean;
  }

  let messages: Msg[] = [
    {
      role: "bot",
      text: "Hai! Saya **Asisten Qlo** (boleh dipanggil **Kulo**). Tanyakan jurusan, kampus, jalur masuk (SNBP/SNBT), atau prospek karier.",
    },
  ];
  let input = "";
  let busy = false;
  let error = "";
  let scroller: HTMLDivElement;

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

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    input = "";
    error = "";
    messages = [...messages, { role: "user", text: q }];
    messages = [...messages, { role: "bot", text: "", typing: true }];
    await scroll();
    busy = true;
    try {
      const reply = await api.post<AssistantReply>("/career/assistant", { message: q });
      messages = [...messages.slice(0, -1), { role: "bot", text: reply.answer }];
    } catch (e) {
      messages = messages.slice(0, -1);
      error = e instanceof ApiError ? e.message : "The assistant is unavailable";
    } finally {
      busy = false;
      await scroll();
    }
  }

  async function scroll() {
    await tick();
    scroller?.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
  }

  onMount(() => {});
</script>

<svelte:head><title>Asisten Qlo — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="mono-label">Panduan Karier · Asisten</p>
      <h1 class="mt-2 font-display text-3xl font-bold">Asisten Qlo</h1>
      <p class="mt-1 text-sm muted">
        Pemandu berbasis aturan (simulasi) untuk pertanyaan belajar & karier — bisa dipanggil
        <span class="font-medium">Kulo</span>.
      </p>
    </div>
    <a href="/career" class="btn-ghost">← Career home</a>
  </div>

  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  <div class="card mt-6 flex h-[60vh] min-h-[420px] flex-col !p-0">
    <div class="flex-1 space-y-3 overflow-y-auto p-5" bind:this={scroller}>
      {#each messages as m}
        <div class="flex items-start gap-3" class:flex-row-reverse={m.role === "user"}>
          <div class="tile-neutral h-7 w-7">
            <Icon
              name={m.role === "bot" ? "robot" : "user"}
              size="13px"
              class={m.role === "bot" ? "text-primary" : ""}
            />
          </div>
          <div
            class="max-w-[80%] rounded-sm px-4 py-2 text-sm"
            class:bg-primary={m.role === "user"}
            class:text-[#05060A]={m.role === "user"}
            class:tone-ink-soft={m.role === "bot"}
            class:dark:bg-surface={m.role === "bot"}
          >
            {#if m.typing}
              <span class="inline-flex gap-1">
                <span class="h-1.5 w-1.5 animate-bounce rounded-sm bg-current"></span>
                <span
                  class="h-1.5 w-1.5 animate-bounce rounded-sm bg-current [animation-delay:0.15s]"
                ></span>
                <span
                  class="h-1.5 w-1.5 animate-bounce rounded-sm bg-current [animation-delay:0.3s]"
                ></span>
              </span>
            {:else}
              <!-- eslint-disable-next-line svelte/no-at-html-tags -->
              <span>{@html render(m.text)}</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    <div class="border-t px-5 py-3">
      <p class="mono-label">Popular questions</p>
      <div class="mt-2 flex flex-wrap gap-2">
        {#each suggestions as s}
          <button class="btn-ghost !py-1 text-xs" on:click={() => send(s)} disabled={busy}
            >{s}</button
          >
        {/each}
      </div>
    </div>

    <div class="flex items-center gap-2 border-t p-4">
      <input
        class="input"
        placeholder="Tanyakan jurusan, kampus, atau karier…"
        bind:value={input}
        on:keydown={(e) => e.key === "Enter" && send()}
        disabled={busy}
      />
      <button class="btn-primary" on:click={() => send()} disabled={busy || !input.trim()}
        >Send</button
      >
    </div>
  </div>
</div>
