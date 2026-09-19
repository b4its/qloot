import { writable } from "svelte/store";
import { browser } from "$app/environment";

export type Theme = "light" | "dark";
const KEY = "qloot-theme";

function initial(): Theme {
  if (!browser) return "light";
  const stored = localStorage.getItem(KEY) as Theme | null;
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function createThemeStore() {
  const { subscribe, set, update } = writable<Theme>(initial());

  function apply(theme: Theme) {
    if (!browser) return;
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(KEY, theme);
  }

  return {
    subscribe,
    init() {
      const t = initial();
      apply(t);
      set(t);
    },
    toggle() {
      update((t) => {
        const next: Theme = t === "dark" ? "light" : "dark";
        apply(next);
        return next;
      });
    },
    set(theme: Theme) {
      apply(theme);
      set(theme);
    },
  };
}

export const theme = createThemeStore();
