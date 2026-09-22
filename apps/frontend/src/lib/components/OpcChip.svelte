<script lang="ts">
  import { onMount } from "svelte";
  import { opc } from "$lib/stores/opc";
  import { formatNumber } from "$lib/utils/format";
  import Icon from "./Icon.svelte";

  /** Compact balance chip shown top-right on every page (teacher & student). */
  export let compact = false;

  onMount(() => opc.refresh());
</script>

<a
  href="/wallet"
  class="wallet-chip group transition-colors hover:border-highlight"
  title="Saldo OryphemToken (OPT)"
  aria-label={`Saldo ${$opc.available} OPT, buka dompet`}
>
  <span class="brand-mark-cool grid h-6 w-6 flex-none place-items-center rounded-sm">
    <Icon name="coins" size="11px" />
  </span>
  <span class="flex flex-col items-start leading-tight">
    {#if !compact}<span class="text-[10px] muted">OPT</span>{/if}
    <span class="font-semibold text-ink">{$opc.available.toLocaleString("id-ID")}</span>
  </span>
  {#if $opc.pending > 0}
    <span
      class="ml-1 inline-flex items-center gap-1 text-[10px] text-highlight"
      title="Menunggu konfirmasi"
    >
      <Icon name="hourglass-half" size="9px" />
      {formatNumber($opc.pending)}
    </span>
  {/if}
</a>
