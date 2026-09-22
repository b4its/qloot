import { readable } from "svelte/store";

// Minimal `$app/navigation` stub for component tests.
export const goto = () => Promise.resolve();
export const invalidate = () => Promise.resolve();
export const invalidateAll = () => Promise.resolve();
export const prefetch = () => Promise.resolve();
export const prefetchRoutes = () => Promise.resolve();
export const beforeNavigate = () => {};
export const afterNavigate = () => {};
export const onNavigate = () => {};
export const pushState = () => {};
export const replaceState = () => {};
export const disableScrollHandling = () => Promise.resolve();
export const navigating = readable(null);
