<script lang="ts">
  /**
   * Shared search box (UIX-04): leading magnifier icon + an explicit clear
   * affordance. The three idioms that existed before (icon-only, ✕-only,
   * bare) are unified here, and `onclear`/`oninput` callbacks let callers
   * reset pagination consistently.
   */
  import Icon from "$lib/components/Icon.svelte";

  /** Two-way bind the query: `bind:value={query}`. */
  export let value = "";
  export let placeholder = "Cari...";
  /** Accessible name; falls back to the placeholder. */
  export let label: string | undefined = undefined;
  /** Fires on every keystroke (use to reset pagination). */
  export let oninput: (() => void) | undefined = undefined;
  /** Fires after the field is cleared. */
  export let onclear: (() => void) | undefined = undefined;
  export let id: string | undefined = undefined;

  function clear() {
    value = "";
    oninput?.();
    onclear?.();
  }
</script>

<div class="relative flex-1 min-w-[180px]">
  <Icon
    name="magnifying-glass"
    size="12px"
    class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 muted"
  />
  <input
    {id}
    type="search"
    class="input text-xs !py-1.5 !pl-8 !pr-8 w-full"
    {placeholder}
    aria-label={label ?? placeholder}
    bind:value
    on:input={() => oninput?.()}
  />
  {#if value}
    <button
      type="button"
      class="absolute right-2 top-1/2 -translate-y-1/2 grid h-5 w-5 place-items-center rounded-xs muted hover:text-ink"
      aria-label="Bersihkan pencarian"
      on:click={clear}
    >
      <Icon name="xmark" size="11px" />
    </button>
  {/if}
</div>
