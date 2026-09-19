<script lang="ts">
  export let variant: "primary" | "success" | "warning" | "danger" | "neutral" = "neutral";
  const classes: Record<string, string> = {
    primary: "bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-100",
    success: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-100",
    warning: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-100",
    danger: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-100",
    neutral: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  };
</script>

<span class={`badge ${classes[variant]}`}><slot /></span>
