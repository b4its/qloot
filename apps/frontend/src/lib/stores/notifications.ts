import { writable } from "svelte/store";
import { api } from "$lib/api/client";

const POLL_MS = 60_000;

function createNotificationStore() {
  const { subscribe, set } = writable<number>(0);
  let timer: ReturnType<typeof setInterval> | null = null;

  function stop() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

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
    /**
     * Begin polling the unread count so the bell stays fresh without a full
     * reload (there is no push channel). Idempotent: repeated calls only keep
     * one timer.
     */
    start() {
      stop();
      void this.refresh();
      timer = setInterval(() => void this.refresh(), POLL_MS);
    },
    stop,
    clear() {
      stop();
      set(0);
    },
  };
}

export const notifications = createNotificationStore();
