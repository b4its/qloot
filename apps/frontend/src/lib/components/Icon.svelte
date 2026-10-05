<script lang="ts">
  import CoinIcon from "./CoinIcon.svelte";

  /**
   * Font Awesome icon wrapper (library icons, no CDN).
   * Usage: <Icon name="graduation-cap" /> · brands: set="brands"
   * Extra classes passed by the consumer are merged in.
   */
  export let name: string;
  export let set: "solid" | "regular" | "brands" = "solid";
  export let size: string | undefined = undefined; // e.g. "1.25em"
  export let label: string | undefined = undefined;
  export let spin = false;
  export let fixedWidth = false;

  $: isCoin = name === "coins" || name === "coin" || name === "currency";
  $: prefix = set === "brands" ? "fa-brands" : set === "regular" ? "fa-regular" : "fa-solid";
  $: classes = [prefix, `fa-${name}`, spin ? "fa-spin" : "", fixedWidth ? "fa-fw" : ""]
    .filter(Boolean)
    .join(" ");
</script>

{#if isCoin}
  <CoinIcon
    size={size ?? "1em"}
    alt={label || "Koin"}
    class="{$$restProps.class || ''} {spin ? 'animate-spin' : ''}"
    {...$$restProps}
  />
{:else}
  <i
    {...$$restProps}
    class="{classes} {$$restProps.class || ''}"
    style={size ? `font-size:${size}` : undefined}
    aria-hidden={label ? undefined : "true"}
    aria-label={label}
    role={label ? "img" : undefined}
  ></i>
{/if}
