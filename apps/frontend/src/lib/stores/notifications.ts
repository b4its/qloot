import { writable } from "svelte/store";
import { api } from "$lib/api/client";

function createNotificationStore() {
  const { subscribe, set } = writable<number>(0);
  return {
    subscribe,
    async refresh() {
      try {
        const res = await api.get<{ unread: number }>("/notifications/unread-count");
        set(res.unread ?? 0);
      } catch {
        set(0);
      }
    },
    clear() {
      set(0);
    },
  };
}

export const notifications = createNotificationStore();
