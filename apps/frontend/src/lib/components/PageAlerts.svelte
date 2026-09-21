<script lang="ts">
  /** Consistent success/error feedback banners used across CRUD pages. */
  import Icon from "$lib/components/Icon.svelte";

  export let message = "";
  export let error = "";
</script>

{#if message}
  <p class="alert-ok mt-4">
    <Icon name="circle-check" size="12px" class="mt-0.5 flex-none" />
    {message}
  </p>
{/if}
{#if error}
  <p class="alert-error mt-4">
    <Icon name="triangle-exclamation" size="12px" class="mt-0.5 flex-none" />
    {error}
  </p>
{/if}
