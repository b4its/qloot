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
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && animate()),
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  });
</script>

<span bind:this={el} class="mono">{display.toLocaleString("id-ID")}{suffix}</span>
