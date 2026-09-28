<script lang="ts" generics="T extends string = string">
  /**
   * Shared segmented filter control (UIX-04). Replaces the ~28 hand-rolled
   * `rounded-sm border p-1` button groups scattered across the app — one
   * consistent look, one consistent accessibility contract.
   *
   * Semantics: rendered as a radio group of toggle buttons so screen readers
   * announce the active filter. `onchange` fires after `value` updates so
   * callers can reset pagination in the same place.
   */
  export let options: readonly (readonly [T, string])[];
  export let value: T;
  /** Two-way bind the value: `bind:value={filter}`. */
  export let onchange: ((next: T) => void) | undefined = undefined;
  /** Accessible name for the group (required when no visible label). */
  export let label: string;
  export let size: "sm" | "md" = "sm";
  export let ariaLabel: string | undefined = undefined;

  function select(next: T) {
    if (next === value) return;
    value = next;
    onchange?.(next);
  }
</script>

<div
  class="flex items-center gap-1 rounded-sm border p-1 surface text-xs"
  role="radiogroup"
  aria-label={ariaLabel ?? label}
>
  {#each options as [val, text] (val)}
    <button
      type="button"
      role="radio"
      aria-checked={value === val}
      class="{size === 'md' ? 'px-3 py-1.5' : 'px-2.5 py-1'} rounded-xs font-medium transition-colors"
      class:bg-primary={value === val}
      class:text-[#05060A]={value === val}
      class:muted={value !== val}
      on:click={() => select(val)}
    >
      {text}
    </button>
  {/each}
</div>
