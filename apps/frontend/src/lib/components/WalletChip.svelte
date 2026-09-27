<script lang="ts">
  import AddressAvatar from "./AddressAvatar.svelte";
  import Icon from "./Icon.svelte";
  import { shortHash } from "$lib/utils/format";

  export let address: string;
  export let label: string | undefined = undefined;
  export let copyable = true;
  export let size = 40;

  let copied = false;
  let copyFailed = false;
  async function copy() {
    if (!copyable) return;
    copyFailed = false;
    if (!navigator.clipboard?.writeText) {
      copyFailed = true;
      setTimeout(() => (copyFailed = false), 2000);
      return;
    }
    try {
      await navigator.clipboard.writeText(address);
      copied = true;
      setTimeout(() => (copied = false), 1400);
    } catch {
      // Never claim success on a blocked clipboard.
      copyFailed = true;
      setTimeout(() => (copyFailed = false), 2000);
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
    <Icon
      name={copied ? "check" : copyFailed ? "triangle-exclamation" : "copy"}
      size="11px"
      class={copyFailed ? "text-danger" : ""}
    />
  {/if}
</button>
{#if copyFailed}
  <span class="sr-only" role="alert" aria-live="assertive"
    >Alamat wallet tidak dapat disalin otomatis.</span
  >
{/if}
