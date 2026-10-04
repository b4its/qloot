import { writable } from "svelte/store";
import { api, API_BASE } from "$lib/api/client";

const POLL_MS = 60_000;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

function createNotificationStore() {
  const { subscribe, set } = writable<number>(0);
  let timer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let socket: WebSocket | null = null;
  let reconnectAttempt = 0;
  let running = false;

  function stop() {
    running = false;
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (socket) {
      socket.onclose = null;
      socket.close();
      socket = null;
    }
    reconnectAttempt = 0;
  }

  function scheduleReconnect() {
    if (!running || reconnectTimer) return;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** reconnectAttempt, RECONNECT_MAX_MS);
    reconnectAttempt += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectSocket();
    }, delay);
  }

  function connectSocket() {
    if (!running || typeof WebSocket === "undefined") return;
    try {
      const wsBase = API_BASE.replace(/^http/, "ws");
      const ws = new WebSocket(`${wsBase}/api/v1/ws/notifications`);
      ws.onopen = () => {
        reconnectAttempt = 0;
      };
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "notification") {
            // A push arrived: the bell should refresh (a full unread-count
            // read is cheap and stays authoritative even if multiple
            // notifications arrive in a burst).
            void store.refresh();
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        if (socket === ws) socket = null;
        scheduleReconnect();
      };
      socket = ws;
    } catch {
      socket = null;
      scheduleReconnect();
    }
  }

  const store = {
    subscribe,
    async refresh() {
      try {
        const res = await api.get<{ unread: number }>("/notifications/unread-count");
        set(res.unread ?? 0);
      } catch {
        // Keep the last authoritative value during transient network failures.
      }
    },
    /**
     * Begin realtime delivery over a per-user WebSocket, with 60s polling as
     * a fallback for when the socket is unavailable (Redis down, network
     * issue): a notification is never lost since it's already persisted;
     * only the "instant" delivery may lag to the next poll. Idempotent.
     */
    start() {
      stop();
      running = true;
      void this.refresh();
      connectSocket();
      timer = setInterval(() => void this.refresh(), POLL_MS);
    },
    stop,
    clear() {
      stop();
      set(0);
    },
  };
  return store;
}

export const notifications = createNotificationStore();
