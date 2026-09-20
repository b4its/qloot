<script lang="ts">
  export let variant: "primary" | "success" | "warning" | "danger" | "neutral" = "neutral";
  const classes: Record<string, string> = {
    primary: "badge-indigo",
    success: "badge-mint",
    warning: "badge-amber",
    danger: "badge-magenta",
    neutral: "badge-neutral",
  };
</script>

<span class={`badge ${classes[variant]}`}><slot /></span>
