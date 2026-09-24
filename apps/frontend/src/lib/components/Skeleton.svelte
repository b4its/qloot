<script lang="ts">
  /**
   * Shared loading skeleton (UIX-03). Use anywhere a list/detail is loading so
   * the placeholder is consistent instead of the bare "Memuat …" text.
   */
  export let rows = 3;
  export let height = "h-8";
  export let label = "Memuat data";
</script>

<div class="space-y-2" role="status" aria-live="polite" aria-label={label}>
  {#each Array(rows) as _}
    <div class="skeleton {height}"></div>
  {/each}
</div>
