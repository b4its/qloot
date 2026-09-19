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
      text: "Hi! I'm the QLoot AI Assistant. Ask me about majors, campuses, admission paths (SNBP/SNBT) or career prospects.",
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

<svelte:head><title>AI Assistant — QLoot</title></svelte:head>

<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold">AI Assistant</h1>
    <p class="mt-1 text-sm muted">A simulated, rule-based guide for study & career questions.</p>
  </div>
  <a href="/career" class="btn-ghost">← Career home</a>
</div>

{#if error}
  <p class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
    {error}
  </p>
{/if}

<div class="card mt-4 flex h-[60vh] min-h-[420px] flex-col !p-0">
  <div class="flex-1 space-y-3 overflow-y-auto p-5" bind:this={scroller}>
    {#each messages as m}
      <div class="flex items-start gap-3" class:flex-row-reverse={m.role === "user"}>
        <div
          class="grid h-7 w-7 flex-none place-items-center rounded-lg bg-slate-100 dark:bg-slate-700"
        >
          <Icon
            name={m.role === "bot" ? "robot" : "user"}
            size="13px"
            klass={m.role === "bot" ? "text-primary" : ""}
          />
        </div>
        <div
          class="max-w-[80%] rounded-2xl px-4 py-2 text-sm"
          class:bg-primary-600={m.role === "user"}
          class:text-white={m.role === "user"}
          class:bg-slate-100={m.role === "bot"}
          class:dark:bg-slate-800={m.role === "bot"}
        >
          {#if m.typing}
            <span class="inline-flex gap-1">
              <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-current"></span>
              <span
                class="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:0.15s]"
              ></span>
              <span
                class="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:0.3s]"
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
    <p class="text-xs font-mono uppercase muted">Popular questions</p>
    <div class="mt-2 flex flex-wrap gap-2">
      {#each suggestions as s}
        <button class="btn-ghost !py-1 text-xs" on:click={() => send(s)} disabled={busy}>{s}</button
        >
      {/each}
    </div>
  </div>

  <div class="flex items-center gap-2 border-t p-4">
    <input
      class="input"
      placeholder="Ask about a major, campus or career…"
      bind:value={input}
      on:keydown={(e) => e.key === "Enter" && send()}
      disabled={busy}
    />
    <button class="btn-primary" on:click={() => send()} disabled={busy || !input.trim()}
      >Send</button
    >
  </div>
</div>
