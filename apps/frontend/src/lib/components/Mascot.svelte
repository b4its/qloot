<script context="module" lang="ts">
  /**
   * Official QLoot Mascot "Qlo" component.
   * Renders high-resolution WebP expressions and poses with rich interactive UX.
   */
  export type MascotExpression =
    | "cool"
    | "happy"
    | "thinking"
    | "excited"
    | "proud"
    | "curious"
    | "determined"
    | "laughing"
    | "wink"
    | "neutral"
    | "surprised"
    | "confused"
    | "sad"
    | "tired"
    | "sleepy"
    | "angry"
    | "embarrassed"
    | "fearful";

  export type MascotPose = "front" | "side" | "back";
  export type MascotCharacter = "qlo" | "qlu" | "cat" | "human";
</script>

<script lang="ts">
  export let character: MascotCharacter = "qlo";
  export let expression: MascotExpression = "cool";
  export let pose: MascotPose = "front";
  export let mode: "expression" | "pose" = "expression";
  export let size: "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "hero" | "custom" = "md";
  export let float = false;
  export let glow = false;
  export let interactive = false;
  export let speech: string | undefined = undefined;
  export let speechPosition: "top" | "right" | "bottom" | "left" = "right";
  export let speechClass = "";
  export let alt: string | undefined = undefined;
  let className = "";
  export { className as class };

  $: isCat = character === "qlu" || character === "cat";
  $: defaultAlt = "Mascot Qlo";
  $: effectiveAlt = alt || defaultAlt;

  $: src = isCat
    ? mode === "pose"
      ? `/mascot/qlu/${pose}.webp`
      : expression === "thinking" || expression === "curious" || expression === "confused"
        ? `/mascot/qlu/side.webp`
        : `/mascot/qlu/front.webp`
    : mode === "pose"
      ? `/mascot/poses/${pose}.webp`
      : `/mascot/expressions/${expression}.webp`;

  $: sizeClasses =
    size === "xs"
      ? "h-7 w-7"
      : size === "sm"
        ? "h-10 w-10"
        : size === "md"
          ? "h-16 w-16"
          : size === "lg"
            ? "h-24 w-24"
            : size === "xl"
              ? "h-36 w-36"
              : size === "2xl"
                ? "h-48 w-48"
                : size === "hero"
                  ? "w-full max-w-[320px] sm:max-w-[400px] h-auto aspect-[1157/1360]"
                  : "";
</script>

<div
  class="relative inline-flex items-center justify-center select-none {className}"
  class:animate-float={float}
  class:transition-transform={interactive}
  class:hover:scale-105={interactive}
>
  <!-- Optional ambient neon backglow -->
  {#if glow}
    <div
      class="absolute inset-0 -z-10 rounded-full bg-gradient-to-tr from-primary/30 to-secondary/30 blur-xl opacity-75"
      aria-hidden="true"
    ></div>
  {/if}

  <!-- Mascot Image -->
  <img
    {src}
    alt={effectiveAlt}
    class="object-contain pointer-events-none {sizeClasses}"
    class:glow-mascot={glow}
    loading="lazy"
    decoding="async"
    draggable="false"
  />

  <!-- Optional Speech Bubble -->
  {#if speech}
    <div
      class="speech-bubble absolute z-20 pointer-events-none whitespace-nowrap rounded-lg border border-primary/30 bg-surface/95 px-3 py-1.5 text-xs font-semibold text-ink shadow-lg backdrop-blur-md dark:border-primary/40 dark:bg-elevated/95 {speechClass} {speechPosition ===
        'top' || speechPosition === 'bottom'
        ? 'left-1/2 -translate-x-1/2'
        : 'top-1/2 -translate-y-1/2'}"
      class:bottom-full={speechPosition === "top"}
      class:mb-2={speechPosition === "top"}
      class:left-full={speechPosition === "right"}
      class:ml-3={speechPosition === "right"}
      class:top-full={speechPosition === "bottom"}
      class:mt-2={speechPosition === "bottom"}
      class:right-full={speechPosition === "left"}
      class:mr-3={speechPosition === "left"}
      role="tooltip"
    >
      <div class="relative">
        {speech}
        <span class="inline-block text-primary ml-1">✦</span>
      </div>
    </div>
  {/if}
</div>
