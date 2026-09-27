<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { auth } from "$lib/stores/auth";
  import { notifications } from "$lib/stores/notifications";
  import { opt } from "$lib/stores/opt";

  // Root layout is intentionally minimal: it only imports global styles and
  // bootstraps shared stores. The chrome (navbar/footer) lives in the child
  // layout groups so the landing page can ship its own navigation.
  //
  // Notification polling and the OPT chip only make sense for a signed-in user;
  // starting them for anonymous visitors means a 401 every poll interval.
  let lastUserId: string | null | undefined;
  const unsubAuth = auth.subscribe((state) => {
    const id = state.loading ? undefined : (state.user?.id ?? null);
    if (id === lastUserId) return;
    lastUserId = id;
    if (id) {
      notifications.start();
      opt.refresh();
    } else if (id === null) {
      notifications.clear();
      opt.reset();
    }
  });

  onMount(() => {
    auth.load();
    return () => {
      unsubAuth();
      notifications.stop();
    };
  });
</script>

<slot />
