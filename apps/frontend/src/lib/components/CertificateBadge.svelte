<script lang="ts">
  import Icon from "./Icon.svelte";

  export let title: string;
  export let subtitle = "";
  export let edition: string | undefined = undefined; // e.g. "#0142 / 5000"
  export let icon = "certificate";
  export let verified = true;
  export let compact = false;
</script>

<div class="nft lift card" class:p-4={compact}>
  <div class="flex items-center justify-between">
    <span
      class="grid h-11 w-11 place-items-center rounded-xl text-white"
      style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
    >
      <Icon name={icon} size="18px" />
    </span>
    {#if verified}
      <span class="badge badge-mint"><Icon name="circle-check" size="11px" /> Terverifikasi</span>
    {/if}
  </div>
  <h3 class="mt-3 font-display text-lg font-bold">{title}</h3>
  {#if subtitle}<p class="text-sm muted">{subtitle}</p>{/if}
  {#if edition}
    <p class="mono-label mt-3">{edition}</p>
  {/if}
  <div class="mt-3 flex items-center gap-2 border-t pt-3 text-xs muted">
    <Icon name="link" size="11px" />
    <span class="mono">Kredensial digital · on-chain ready</span>
  </div>
</div>
