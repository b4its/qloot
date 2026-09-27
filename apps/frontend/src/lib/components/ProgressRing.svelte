<script lang="ts">
  export let value = 0; // 0..100
  export let size = 120;
  export let stroke = 10;
  export let label = "";
  export let sublabel = "";

  // Unique gradient id: hardcoding one id duplicates across multiple rings on
  // the same page (invalid DOM, wrong gradient resolution).
  const gradId = `ringGrad-${Math.random().toString(36).slice(2, 9)}`;

  $: r = (size - stroke) / 2;
  $: c = 2 * Math.PI * r;
  $: offset = c * (1 - Math.min(100, Math.max(0, value)) / 100);
</script>

<div class="relative grid place-items-center" style={`width:${size}px;height:${size}px`}>
  <svg
    width={size}
    height={size}
    class="-rotate-90"
    role="progressbar"
    aria-valuenow={Math.round(value)}
    aria-valuemin={0}
    aria-valuemax={100}
    aria-label={label ? `${label}: ${Math.round(value)}%` : `Progres ${Math.round(value)}%`}
  >
    <defs>
      <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#FCEE0A" />
        <stop offset="100%" stop-color="#00F0FF" />
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
      stroke={`url(#${gradId})`}
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
