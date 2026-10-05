<script lang="ts">
  import { onMount } from "svelte";

  export let title: string;
  export let description = "";
  export let titleId = "app-dialog-title";
  export let descriptionId = "app-dialog-description";
  export let busy = false;
  export let close: () => void;
  export let size = "max-w-lg";

  let panel: HTMLDivElement;
  let opener: HTMLElement | null = null;
  let previousOverflow = "";

  const focusableSelector =
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  onMount(() => {
    opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusFrame = requestAnimationFrame(() => {
      if (!panel) return;
      const initial =
        panel.querySelector<HTMLElement>("[data-autofocus]") ??
        panel.querySelector<HTMLElement>(focusableSelector);
      initial?.focus();
    });

    return () => {
      cancelAnimationFrame(focusFrame);
      document.body.style.overflow = previousOverflow;
      if (opener?.isConnected) opener.focus();
    };
  });

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      if (!busy) close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(panel.querySelectorAll<HTMLElement>(focusableSelector));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget && !busy) {
      close();
    }
  }
</script>

<svelte:window on:keydown={onKeydown} />

<div
  class="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs"
  on:click={handleBackdropClick}
  role="presentation"
>
  <div
    bind:this={panel}
    class="card flex max-h-[90dvh] w-full {size} flex-col overflow-hidden border-primary/40 shadow-2xl"
    role="dialog"
    aria-modal="true"
    aria-labelledby={titleId}
    aria-describedby={description ? descriptionId : undefined}
    tabindex="-1"
  >
    <div class="flex flex-none items-start justify-between gap-4 border-b pb-3">
      <div>
        <h2 id={titleId} class="hud font-display text-lg font-bold">{title}</h2>
        {#if description}
          <p id={descriptionId} class="mt-1 text-xs muted">{description}</p>
        {/if}
      </div>
      <button class="btn-icon flex-none" on:click={close} disabled={busy} aria-label="Tutup dialog">
        ×
      </button>
    </div>
    <div class="min-h-0 flex-1 overflow-y-auto py-4">
      <slot />
    </div>
    <div class="flex-none border-t pt-3">
      <slot name="footer" />
    </div>
  </div>
</div>
