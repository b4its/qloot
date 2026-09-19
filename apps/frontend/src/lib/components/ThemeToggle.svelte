<script lang="ts">
  import { onMount } from "svelte";
  import { theme } from "$lib/stores/theme";

  onMount(() => theme.init());
</script>

<button
  class="btn-ghost h-9 w-9 !px-0"
  aria-label="Toggle color theme"
  title="Toggle theme"
  on:click={() => theme.toggle()}
>
  {#if $theme === "dark"}
    <span aria-hidden="true">☀️</span>
  {:else}
    <span aria-hidden="true">🌙</span>
  {/if}
</button>
