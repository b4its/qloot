<script lang="ts">
  import { onMount } from "svelte";
  import { opt } from "$lib/stores/opt";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "./Icon.svelte";

  /** Compact balance chip shown top-right on every page (teacher & student). */
  export let compact = false;

  let prevAvailable: number | null = null;
  let diff = 0;
  let flash = false;
  let flashTimer: ReturnType<typeof setTimeout> | null = null;

  $: {
    const cur = $opt.available;
    if (prevAvailable !== null && cur > prevAvailable && $opt.loaded) {
      diff = cur - prevAvailable;
      flash = true;
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(() => {
        flash = false;
      }, 2500);
    }
    if ($opt.loaded) {
      prevAvailable = cur;
    }
  }

  onMount(() => opt.refresh());
</script>

<a
  href="/wallet"
  class="wallet-chip group relative transition-all duration-300 hover:border-highlight"
  class:ring-2={flash}
  class:ring-mint={flash}
  title="Saldo OryphemToken (OPT)"
  aria-label={`Saldo ${$opt.available} OPT, buka dompet`}
>
  <span class="brand-mark-cool grid h-6 w-6 flex-none place-items-center rounded-sm">
    <Icon name="coins" size="11px" />
  </span>
  <span class="flex flex-col items-start leading-tight">
    {#if !compact}<span class="text-[10px] muted">OPT</span>{/if}
    <span class="font-semibold text-ink">{$opt.available.toLocaleString("id-ID")}</span>
  </span>
  {#if $opt.pending > 0}
    <span
      class="ml-1 inline-flex items-center gap-1 text-[10px] text-highlight"
      title="Menunggu konfirmasi"
    >
      <Icon name="hourglass-half" size="9px" />
      {formatNumber($opt.pending)}
    </span>
  {/if}
  {#if flash && diff > 0}
    <span
      class="badge-mint absolute -bottom-3 right-0 animate-bounce rounded px-1 py-0 text-[10px] font-bold shadow-sm"
    >
      +{diff.toLocaleString("id-ID")}
    </span>
  {/if}
</a>
