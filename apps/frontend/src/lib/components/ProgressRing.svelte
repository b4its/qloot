<script lang="ts">
  export let value = 0; // 0..100
  export let size = 120;
  export let stroke = 10;
  export let label = "";
  export let sublabel = "";

  $: r = (size - stroke) / 2;
  $: c = 2 * Math.PI * r;
  $: offset = c * (1 - Math.min(100, Math.max(0, value)) / 100);
</script>

<div class="relative grid place-items-center" style={`width:${size}px;height:${size}px`}>
  <svg width={size} height={size} class="-rotate-90" role="img" aria-label={`${label} ${value}%`}>
    <defs>
      <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#5B48FF" />
        <stop offset="100%" stop-color="#00E5A8" />
      </linearGradient>
    </defs>
    <circle
      cx={size / 2}
      cy={size / 2}
      {r}
      fill="none"
      stroke="rgb(var(--line))"
      stroke-width={stroke}
    />
    <circle
      cx={size / 2}
      cy={size / 2}
      {r}
      fill="none"
      stroke="url(#ringGrad)"
      stroke-width={stroke}
      stroke-linecap="round"
      stroke-dasharray={c}
      stroke-dashoffset={offset}
      style="transition: stroke-dashoffset .8s cubic-bezier(0.22,1,0.36,1)"
    />
  </svg>
  <div class="absolute grid place-items-center text-center">
    <span class="font-display text-xl font-bold">{Math.round(value)}%</span>
    {#if label}<span class="mono-label">{label}</span>{/if}
    {#if sublabel}<span class="text-[11px] muted">{sublabel}</span>{/if}
  </div>
</div>
