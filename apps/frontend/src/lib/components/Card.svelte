<script lang="ts">
  export let title: string | undefined = undefined;
  export let subtitle: string | undefined = undefined;
</script>

<section class="card">
  {#if title}
    <header class="mb-3">
      <h2 class="text-lg font-semibold">{title}</h2>
      {#if subtitle}<p class="text-sm muted">{subtitle}</p>{/if}
    </header>
  {/if}
  <slot />
</section>
