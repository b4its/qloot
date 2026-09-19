<script lang="ts">
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

  $: prefix = set === "brands" ? "fa-brands" : set === "regular" ? "fa-regular" : "fa-solid";
  $: classes = [prefix, `fa-${name}`, spin ? "fa-spin" : "", fixedWidth ? "fa-fw" : ""]
    .filter(Boolean)
    .join(" ");
</script>

<i
  {...$$restProps}
  class="{classes} {$$restProps.class || ''}"
  style={size ? `font-size:${size}` : undefined}
  aria-hidden={label ? undefined : "true"}
  aria-label={label}
  role={label ? "img" : undefined}
></i>
