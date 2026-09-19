<script lang="ts">
  import AddressAvatar from "./AddressAvatar.svelte";
  import Icon from "./Icon.svelte";
  import { shortHash } from "$lib/utils/format";

  export let address: string;
  export let label: string | undefined = undefined;
  export let copyable = true;
  export let size = 40;

  let copied = false;
  async function copy() {
    if (!copyable) return;
    try {
      await navigator.clipboard.writeText(address);
      copied = true;
      setTimeout(() => (copied = false), 1400);
    } catch {
      /* ignore */
    }
  }
</script>

<button
  class="wallet-chip transition-colors hover:border-primary"
  on:click={copy}
  title={address}
  aria-label={`Alamat wallet ${address}${copyable ? ", klik untuk salin" : ""}`}
  type="button"
>
  <AddressAvatar seed={address} {size} />
  <span class="flex flex-col items-start leading-tight">
    {#if label}<span class="text-[10px] muted">{label}</span>{/if}
    <span class="text-ink">{shortHash(address, 6)}</span>
  </span>
  {#if copyable}
    <Icon name={copied ? "check" : "copy"} size="11px" />
  {/if}
</button>
