<script lang="ts">
  /**
   * Reusable pager. Two modes:
   *  - total mode: pass `total`; renders "X–Y of N" with a page counter.
   *  - cursor mode: pass `hasMore` (list endpoints that return just an array);
   *    renders Prev/Next and reports the page number.
   *
   * The parent owns the data and offset state; this only calls `onPrev`/`onNext`.
   */
  import Icon from "$lib/components/Icon.svelte";

  export let page = 1;
  export let pageSize = 20;
  /** Total rows, when the API reports it. */
  export let total: number | undefined = undefined;
  /** For total-less endpoints: whether another page may exist. */
  export let hasMore: boolean | undefined = undefined;
  export let loading = false;
  export let label = "data";
  export let onPrev: () => void = () => {};
  export let onNext: () => void = () => {};

  $: totalPages = total !== undefined ? Math.max(1, Math.ceil(total / pageSize)) : undefined;
  $: canPrev = page > 1 && !loading;
  $: canNext =
    totalPages !== undefined ? page < totalPages && !loading : hasMore === true && !loading;
  $: rangeStart = (page - 1) * pageSize + 1;
  $: rangeEnd = total !== undefined ? Math.min(page * pageSize, total) : page * pageSize;
  $: visible = total !== undefined ? total > pageSize : hasMore !== undefined;
</script>

{#if visible}
  <div class="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
    <p class="muted">
      {#if total !== undefined}
        {rangeStart}–{rangeEnd} dari {total} {label}
      {:else}
        {label} · halaman {page}
      {/if}
    </p>
    <div class="flex items-center gap-2">
      <button class="btn-ghost !py-1.5" on:click={onPrev} disabled={!canPrev}>
        <Icon name="chevron-left" size="11px" /> Sebelumnya
      </button>
      <span class="mono-label">
        {#if totalPages !== undefined}Hal. {page}/{totalPages}{:else}Hal. {page}{/if}
      </span>
      <button class="btn-ghost !py-1.5" on:click={onNext} disabled={!canNext}>
        Berikutnya <Icon name="chevron-right" size="11px" />
      </button>
    </div>
  </div>
{/if}
