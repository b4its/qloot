<script lang="ts">
  /**
   * Shared destructive/irreversible-action confirmation modal.
   *
   * Replaces native `confirm()`/`prompt()` so confirmations are themed,
   * focus-trapped, keyboard accessible (Esc to cancel), and can host an
   * optional reason/note input. Built on top of the accessible Dialog shell.
   */
  import Dialog from "$lib/components/Dialog.svelte";
  import Icon from "$lib/components/Icon.svelte";

  export let title: string;
  export let description = "";
  /** Optional extra explanatory line rendered under the description. */
  export let hint = "";
  export let confirmLabel = "Ya, Lanjutkan";
  export let cancelLabel = "Batal";
  export let busy = false;
  /** `danger` (default) for destructive actions, `primary` for neutral ones. */
  export let tone: "danger" | "primary" = "danger";
  /** When set, renders an optional reason/note textarea bound to this value. */
  export let reason: string | null = null;
  export let reasonLabel = "Alasan (opsional)";
  export let reasonPlaceholder = "";
  /** Called on every keystroke with the current reason (two-way via callback). */
  export let onReason: ((value: string) => void) | undefined = undefined;
  /** Optional `data-role` for the confirm button (for tests/analytics). */
  export let confirmRole = "confirm-action";
  export let onConfirm: () => void;
  export let close: () => void;

  // Svelte props are one-way: bind the textarea to a local draft and push
  // changes back through `onReason` so the parent's state stays authoritative.
  let reasonDraft = reason ?? "";
  $: if (reason !== null && reason !== reasonDraft) reasonDraft = reason;
  function onReasonInput() {
    onReason?.(reasonDraft);
  }

  function confirm() {
    if (busy) return;
    onConfirm();
  }
</script>

<Dialog {title} {description} size="max-w-md" {busy} {close}>
  <div class="space-y-4">
    {#if tone === "danger"}
      <div class="flex items-start gap-3">
        <span
          class="mt-0.5 grid h-9 w-9 flex-none place-items-center rounded-sm bg-danger/15 text-danger"
        >
          <Icon name="triangle-exclamation" size="16px" />
        </span>
        {#if hint}
          <p class="text-sm leading-relaxed text-ink2">{hint}</p>
        {/if}
      </div>
    {:else if hint}
      <p class="text-sm leading-relaxed text-ink2">{hint}</p>
    {/if}

    {#if reason !== null}
      <label class="block">
        <span class="mono-label text-[10px]">{reasonLabel}</span>
        <textarea
          class="input mt-1 w-full text-sm"
          rows="2"
          placeholder={reasonPlaceholder}
          bind:value={reasonDraft}
          on:input={onReasonInput}
          data-autofocus
        ></textarea>
      </label>
    {/if}
  </div>

  <svelte:fragment slot="footer">
    <div class="flex items-center justify-end gap-2">
      <button class="btn-ghost text-xs" on:click={close} disabled={busy}>{cancelLabel}</button>
      <button
        class={tone === "danger"
          ? "btn-primary !bg-danger !text-white text-xs font-semibold"
          : "btn-primary text-xs font-semibold"}
        on:click={confirm}
        disabled={busy}
        data-role={confirmRole}
        data-autofocus={reason === null ? "" : undefined}
      >
        {#if busy}<Icon name="spinner" spin size="11px" />{/if}
        {confirmLabel}
      </button>
    </div>
  </svelte:fragment>
</Dialog>
