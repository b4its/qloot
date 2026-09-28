<script lang="ts" context="module">
  /** A single KPI card in the strip. */
  export type Metric = {
    label: string;
    value: string | number;
    /** Tailwind text-* tone class for the value (e.g. "text-mint"). */
    tone?: string;
    sub?: string;
    /** data-role for tests, forwarded to the value element. */
    role?: string;
  };
</script>

<script lang="ts">
  /**
   * Shared KPI strip (UIX-04): the `grid grid-cols-2 sm:grid-cols-4` row of
   * cards repeated on courses, exams, learning, badges, tasks, ranking,
   * notifications, quests, certificates, and the panel hubs.
   *
   * Pass an array of `{ label, value, tone?, sub? }`; the grid adapts to the
   * number of metrics (capped at four columns for readability).
   */
  export let metrics: Metric[] = [];
  export let columns: 2 | 3 | 4 = 4;
</script>

{#if metrics.length}
  <div
    class="mt-6 grid grid-cols-2 gap-3"
    class:sm:grid-cols-3={columns === 3}
    class:sm:grid-cols-4={columns === 4}
  >
    {#each metrics as m (m.label)}
      <div class="card p-4">
        <p class="mono-label text-[10px]">{m.label}</p>
        <p class="mt-1 font-display text-3xl font-bold {m.tone ?? ''}" data-role={m.role}>
          {m.value}
        </p>
        {#if m.sub}<p class="mt-0.5 text-xs muted">{m.sub}</p>{/if}
      </div>
    {/each}
  </div>
{/if}
