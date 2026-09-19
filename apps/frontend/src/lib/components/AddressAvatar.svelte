<script lang="ts">
  /** Deterministic generative "blocky" avatar derived from an address/hash. */
  export let seed: string = "0x0000";
  export let size = 40;

  // FNV-1a hash → stable pseudo-random stream.
  function hash(str: string): number {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  $: h = hash(seed);
  $: cells = Array.from({ length: 15 }, (_, i) => ((h >>> i) ^ (h * (i + 3))) % 7 === 0);
  // Mirror the 3x5 grid horizontally for a symmetric "identicon" look.
  $: grid = [0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2];
  $: hue = h % 360;
</script>

<span
  class="addr-avatar grid overflow-hidden"
  style={`width:${size}px;height:${size}px;background:linear-gradient(135deg,hsl(${hue} 70% 55%),hsl(${(hue + 60) % 360} 70% 50%))`}
  role="img"
  aria-label="Avatar wallet"
>
  <span class="grid h-full w-full grid-cols-3 grid-rows-5 gap-[1px] p-[2px]">
    {#each grid as g, i}
      <span
        class="rounded-[1px]"
        style={`background:${cells[i] || cells[14 - i] ? "rgba(255,255,255,.85)" : "transparent"}`}
      ></span>
    {/each}
  </span>
</span>
