<script lang="ts">
  /**
   * Official QLoot Brand Logo component.
   * Seamlessly adapts to dark ("Night City") and light theme surfaces.
   */
  export let variant: "full" | "symbol" | "icon" | "vertical" = "full";
  export let height = "h-7";
  export let alt = "QLoot";
  export let href = "/";
  export let asLink = false;
  let className = "";
  export { className as class };

  $: lightSrcWebp =
    variant === "full"
      ? "/brand/logo-light.webp"
      : variant === "symbol"
        ? "/brand/symbol-light.webp"
        : variant === "vertical"
          ? "/brand/logo-vertical-light.webp"
          : "/brand/icon-light.webp";

  $: lightSrcPng =
    variant === "full"
      ? "/brand/logo-light.png"
      : variant === "symbol"
        ? "/brand/symbol-light.png"
        : variant === "vertical"
          ? "/brand/logo-vertical-light.png"
          : "/brand/icon-light.png";

  $: darkSrcWebp =
    variant === "full"
      ? "/brand/logo-dark.webp"
      : variant === "symbol"
        ? "/brand/symbol-dark.webp"
        : variant === "vertical"
          ? "/brand/logo-vertical-dark.webp"
          : "/brand/icon-dark.webp";

  $: darkSrcPng =
    variant === "full"
      ? "/brand/logo-dark.png"
      : variant === "symbol"
        ? "/brand/symbol-dark.png"
        : variant === "vertical"
          ? "/brand/logo-vertical-dark.png"
          : "/brand/icon-dark.png";
</script>

{#if asLink}
  <a
    {href}
    class="brand-logo-link inline-flex items-center transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary {className}"
    aria-label={alt}
  >
    <!-- Light Mode Logo -->
    <picture class="inline-block dark:hidden" aria-hidden="true">
      <source srcset={lightSrcWebp} type="image/webp" />
      <img
        src={lightSrcPng}
        alt=""
        class="{height} w-auto object-contain select-none"
        loading="eager"
        decoding="async"
        draggable="false"
      />
    </picture>

    <!-- Dark Mode Logo -->
    <picture class="hidden dark:inline-block" aria-hidden="true">
      <source srcset={darkSrcWebp} type="image/webp" />
      <img
        src={darkSrcPng}
        alt=""
        class="{height} w-auto object-contain select-none"
        loading="eager"
        decoding="async"
        draggable="false"
      />
    </picture>
  </a>
{:else}
  <span class="brand-logo inline-flex items-center {className}" role="img" aria-label={alt}>
    <!-- Light Mode Logo -->
    <picture class="inline-block dark:hidden" aria-hidden="true">
      <source srcset={lightSrcWebp} type="image/webp" />
      <img
        src={lightSrcPng}
        alt=""
        class="{height} w-auto object-contain select-none"
        loading="eager"
        decoding="async"
        draggable="false"
      />
    </picture>

    <!-- Dark Mode Logo -->
    <picture class="hidden dark:inline-block" aria-hidden="true">
      <source srcset={darkSrcWebp} type="image/webp" />
      <img
        src={darkSrcPng}
        alt=""
        class="{height} w-auto object-contain select-none"
        loading="eager"
        decoding="async"
        draggable="false"
      />
    </picture>
  </span>
{/if}
