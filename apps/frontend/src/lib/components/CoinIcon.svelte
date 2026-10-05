<script lang="ts">
  /**
   * Universal Coin / Currency Icon for QLoot platform.
   * Renders the official QLoot coin icon (coinIcon.webp).
   */
  export let size: string = "1em";
  export let alt: string = "Koin";
  export let className: string = "";
  export { className as class };
</script>

<img
  src="/coin/coinIcon.webp"
  {alt}
  class="inline-block object-contain select-none shrink-0 align-middle {className}"
  style="width:{size};height:{size};"
  loading="eager"
  decoding="async"
  draggable="false"
  {...$$restProps}
/>
