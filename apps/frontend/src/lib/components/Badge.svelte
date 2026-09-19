<script lang="ts">
  export let variant: "primary" | "success" | "warning" | "danger" | "neutral" = "neutral";
  const classes: Record<string, string> = {
    primary: "bg-primary/15 text-primary dark:bg-primary-900 dark:text-primary-100",
    success: "bg-green-100 text-secondary dark:bg-green-900 dark:text-green-100",
    warning: "bg-highlight/20 text-highlight dark:bg-amber-900 dark:text-amber-100",
    danger: "bg-tertiary/15 text-tertiary dark:bg-red-900 dark:text-red-100",
    neutral: "bg-ink/5 text-ink2 dark:bg-surface",
  };
</script>

<span class={`badge ${classes[variant]}`}><slot /></span>
