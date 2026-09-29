<script lang="ts">
  import { onMount } from "svelte";

  export let value = 0;
  export let duration = 1200;
  export let suffix = "";

  let display = 0;
  let el: HTMLSpanElement;
  // Whether the counter has entered the viewport (or the fallback fired).
  let started = false;
  // The value the current animation is heading towards, so a late-arriving
  // real value (stats load async) is not dropped after the first run.
  let animatedTo: number | null = null;
  let rafId: number | null = null;

  function animate() {
    if (!started) return;
    if (animatedTo === value) return;
    animatedTo = value;
    if (rafId !== null) cancelAnimationFrame(rafId);
    const from = display;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      display = value;
      return;
    }
    // Anchor the clock on the FIRST frame's timestamp rather than a separate
    // performance.now() call: a requestAnimationFrame shim (or any clock skew)
    // can hand back a timestamp earlier than a previously captured now(), which
    // would make elapsed time negative forever and stall the counter at 0.
    let start: number | null = null;
    function frame(now: number) {
      if (start === null) start = now;
      const t = Math.max(0, Math.min(1, (now - start) / duration));
      const eased = 1 - Math.pow(1 - t, 3);
      display = Math.round(from + (value - from) * eased);
      if (t < 1) rafId = requestAnimationFrame(frame);
      else {
        display = value;
        rafId = null;
      }
    }
    rafId = requestAnimationFrame(frame);
  }

  // Re-animate whenever the target value changes after the counter has started
  // (e.g. community stats render at 0, then the fetch resolves).
  $: if (started && value !== animatedTo) animate();

  onMount(() => {
    if (!el || typeof IntersectionObserver === "undefined") {
      started = true;
      animate();
      return;
    }
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            started = true;
            animate();
          }
        }),
      { threshold: 0.3 },
    );
    io.observe(el);
    // Safety net: if the element is already visible but the observer never
    // fires (e.g. a display:none ancestor), still show the real value.
    const fallback = setTimeout(() => {
      started = true;
      animate();
    }, 1500);
    return () => {
      io.disconnect();
      clearTimeout(fallback);
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  });
</script>

<span bind:this={el} class="mono" aria-label={`${value.toLocaleString("id-ID")}${suffix}`}>
  <span aria-hidden="true">{display.toLocaleString("id-ID")}{suffix}</span>
</span>
