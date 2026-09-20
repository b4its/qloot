<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { auth } from "$lib/stores/auth";
  import { notifications } from "$lib/stores/notifications";
  import { opc } from "$lib/stores/opc";

  // Root layout is intentionally minimal: it only imports global styles and
  // bootstraps shared stores. The chrome (navbar/footer) lives in the child
  // layout groups so the landing page can ship its own navigation.
  onMount(() => {
    auth.load();
    notifications.refresh();
    opc.refresh();
  });
</script>

<slot />
