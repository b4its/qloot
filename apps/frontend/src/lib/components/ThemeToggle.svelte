<script lang="ts">
  import { onMount } from "svelte";
  import { theme } from "$lib/stores/theme";
  import Icon from "./Icon.svelte";

  export let variant: "icon" | "full" = "icon";

  onMount(() => theme.init());
</script>

{#if variant === "icon"}
  <button
    class="btn-icon relative"
    aria-label="Ganti tema tampilan"
    title="Ganti tema"
    on:click={() => theme.toggle()}
  >
    <span class="relative grid h-4 w-4 place-items-center">
      {#if $theme === "dark"}
        <Icon name="moon" size="16px" class="text-secondary" />
      {:else}
        <Icon name="sun" size="16px" class="text-highlight" />
      {/if}
    </span>
  </button>
{:else}
  <button
    class="btn-ghost w-full !justify-start"
    on:click={() => theme.toggle()}
    aria-label="Ganti tema tampilan"
  >
    {#if $theme === "dark"}
      <Icon name="moon" /> <span>Mode Gelap</span>
    {:else}
      <Icon name="sun" /> <span>Mode Terang</span>
    {/if}
  </button>
{/if}
