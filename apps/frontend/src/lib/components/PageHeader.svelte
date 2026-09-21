<script lang="ts">
  /**
   * Consistent page header for the teacher/admin (and other) sections.
   * Renders the eyebrow (mono-label), title, optional subtitle, an optional
   * primary action link, and an optional right-aligned back-link.
   */
  import Icon from "$lib/components/Icon.svelte";

  export let eyebrow: string;
  export let title: string;
  export let subtitle: string | undefined = undefined;
  export let backHref: string | undefined = undefined;
  export let backLabel = "Kembali";
  export let actionHref: string | undefined = undefined;
  export let actionLabel: string | undefined = undefined;
  export let actionIcon = "plus";
</script>

<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <p class="mono-label">{eyebrow}</p>
    <h1 class="mt-2 font-display text-3xl font-bold sm:text-4xl">{title}</h1>
    {#if subtitle}<p class="mt-2 max-w-2xl muted">{subtitle}</p>{/if}
  </div>
  <div class="flex items-center gap-2">
    {#if actionHref && actionLabel}
      <a href={actionHref} class="btn-primary">
        <Icon name={actionIcon} size="12px" />
        {actionLabel}
      </a>
    {/if}
    {#if backHref}
      <a href={backHref} class="btn-ghost">
        <Icon name="arrow-left" size="11px" />
        {backLabel}
      </a>
    {/if}
  </div>
</div>
