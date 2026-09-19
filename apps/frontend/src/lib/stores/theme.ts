import { writable } from "svelte/store";
import { browser } from "$app/environment";

export type Theme = "light" | "dark";
const KEY = "qloot-theme";

function safeStorage(): Storage | null {
  try {
    if (!browser || typeof localStorage === "undefined") return null;
    return localStorage;
  } catch {
    return null;
  }
}

function initial(): Theme {
  const stored = safeStorage()?.getItem(KEY) as Theme | null;
  if (stored === "light" || stored === "dark") return stored;
  try {
    if (browser && typeof window !== "undefined" && window.matchMedia) {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
  } catch {
    /* ignore */
  }
  return "light";
}

function createThemeStore() {
  const { subscribe, set, update } = writable<Theme>("light");

  function apply(theme: Theme) {
    try {
      document.documentElement.classList.toggle("dark", theme === "dark");
      safeStorage()?.setItem(KEY, theme);
    } catch {
      /* ignore */
    }
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
