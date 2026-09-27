<script lang="ts">
  import { onMount } from "svelte";

  export let value = 0;
  export let duration = 1200;
  export let suffix = "";

  let display = 0;
  let el: HTMLSpanElement;
  let done = false;

  function animate() {
    if (done) return;
    done = true;
    const start = performance.now();
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      display = value;
      return;
    }
    function frame(now: number) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      display = Math.round(value * eased);
      if (t < 1) requestAnimationFrame(frame);
      else display = value;
    }
    requestAnimationFrame(frame);
  }

  onMount(() => {
    if (!el) {
      animate();
      return;
    }
    // Fallback: if IntersectionObserver is unavailable, never leave the
    // counter stuck at a misleading "0".
    if (typeof IntersectionObserver === "undefined") {
      animate();
      return;
    }
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) animate();
        }),
      { threshold: 0.3 },
    );
    io.observe(el);
    // Safety net: if the element is already visible but the observer never
    // fires (e.g. a display:none ancestor), still show the real value.
    const fallback = setTimeout(() => animate(), 1500);
    return () => {
      io.disconnect();
      clearTimeout(fallback);
    };
  });
</script>

<span bind:this={el} class="mono">{display.toLocaleString("id-ID")}{suffix}</span>
