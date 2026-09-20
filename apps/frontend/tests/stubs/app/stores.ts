import { readable } from "svelte/store";

// Minimal `$app/stores` stub for component tests. Exposes a `page` store with
// the same shape used across the app (url, params, status, data, error).
export const page = readable({
  url: new URL("http://localhost:3000/"),
  params: {},
  route: { id: "/" },
  status: 200,
  error: null,
  data: {},
  state: {},
});

export const navigating = readable(null);
export const updated = readable(false);
