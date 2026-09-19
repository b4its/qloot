import { writable } from "svelte/store";
import { api } from "$lib/api/client";

export interface OpcState {
  available: number;
  pending: number;
  loaded: boolean;
}

function createOpcStore() {
  const { subscribe, set, update } = writable<OpcState>({
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

export const opc = createOpcStore();
