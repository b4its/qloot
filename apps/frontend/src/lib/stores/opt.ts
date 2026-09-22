import { writable } from "svelte/store";
import { api } from "$lib/api/client";

/** The caller's OPT base-currency balance (mirrors GET /wallet). */
export interface OptState {
  available: number;
  pending: number;
  loaded: boolean;
}

function createOptStore() {
  const { subscribe, set, update } = writable<OptState>({
    available: 0,
    pending: 0,
    loaded: false,
  });
  return {
    subscribe,
    async refresh() {
      try {
        const w = await api.get<{ available: number; pending: number }>("/wallet");
        set({ available: w.available ?? 0, pending: w.pending ?? 0, loaded: true });
      } catch {
        update((s) => ({ ...s, loaded: true }));
      }
    },
    reset() {
      set({ available: 0, pending: 0, loaded: false });
    },
  };
}

export const opt = createOptStore();
