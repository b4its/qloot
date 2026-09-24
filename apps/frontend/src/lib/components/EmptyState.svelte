<script lang="ts">
  /**
   * Shared empty/error state (UIX-03): a consistent message + optional action
   * used across list pages so empty states stop diverging.
   */
  import Icon from "$lib/components/Icon.svelte";

  export let icon = "inbox";
  export let title = "Belum ada data";
  export let description = "";
  export let actionHref: string | undefined = undefined;
  export let actionLabel: string | undefined = undefined;
  /** "empty" | "error" */
  export let tone: "empty" | "error" = "empty";
</script>

<div class="card mt-4 grid place-items-center py-12 text-center" role="status">
  <Icon
    name={tone === "error" ? "triangle-exclamation" : icon}
    size="26px"
    class={tone === "error" ? "text-tertiary" : "muted"}
  />
  <p class="mt-3 font-semibold">{title}</p>
  {#if description}<p class="mt-1 text-sm muted">{description}</p>{/if}
  {#if actionHref && actionLabel}
    <a href={actionHref} class="btn-primary mt-4">{actionLabel}</a>
  {/if}
</div>
