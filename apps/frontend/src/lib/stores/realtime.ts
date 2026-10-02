import { writable } from "svelte/store";
import { opt } from "./opt";

export interface RealtimeMessage {
  type: string;
  kind?: string;
  asset?: string;
  balance?: number;
  amount?: number;
  entry_type?: string;
  reference_type?: string;
  title?: string;
  body?: string;
  data?: any;
  [key: string]: any;
}

export type RealtimeListener = (message: RealtimeMessage) => void;
export type RealtimeFilter = string | string[] | ((msg: RealtimeMessage) => boolean);

interface ListenerEntry {
  filter: (message: RealtimeMessage) => boolean;
  callback: RealtimeListener;
}

const listeners = new Set<ListenerEntry>();

export const realtimeEvent = writable<{ event: RealtimeMessage | null; timestamp: number }>({
  event: null,
  timestamp: 0,
});

/**
 * Register a listener for real-time events.
 * Returns an unsubscribe callback for easy cleanup in onMount.
 */
export function onRealtime(filter: RealtimeFilter, callback: RealtimeListener): () => void {
  const filterFn =
    typeof filter === "function"
      ? filter
      : (msg: RealtimeMessage) => {
          const list = Array.isArray(filter) ? filter : [filter];
          return list.some((f) => {
            if (f.startsWith("notification:")) {
              const expectedKind = f.slice("notification:".length);
              return msg.type === "notification" && msg.kind === expectedKind;
            }
            return msg.type === f;
          });
        };

  const entry: ListenerEntry = { filter: filterFn, callback };
  listeners.add(entry);

  return () => {
    listeners.delete(entry);
  };
}

/**
 * Dispatches an incoming WebSocket event across stores, registered listeners,
 * and the browser window event bus.
 */
export function dispatchRealtimeMessage(message: RealtimeMessage): void {
  realtimeEvent.set({ event: message, timestamp: Date.now() });

  // 1. Reactive store updates
  if (message.type === "wallet.updated") {
    if (message.asset === "OPT" && typeof message.balance === "number") {
      opt.setBalance(message.balance);
    }
    void opt.refresh();
  } else if (message.type === "notification") {
    // The notification store refreshes its own unread count (it owns the
    // WebSocket that receives these frames); here we only fan out the OPT
    // refresh for reward-like notifications. Avoid importing the notification
    // store statically to keep this module free of a circular dependency.
    const kind = message.kind;
    if (kind && ["reward", "quest", "level", "badge", "task"].includes(kind)) {
      void opt.refresh();
    }
  } else if (message.type === "withdrawal.updated") {
    void opt.refresh();
  }

  // 2. Notify subscribers
  for (const entry of Array.from(listeners)) {
    try {
      if (entry.filter(message)) {
        entry.callback(message);
      }
    } catch (err) {
      console.error("[Realtime] error in listener callback:", err);
    }
  }

  // 3. Dispatch window CustomEvent for external consumers/tests
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("qloot:realtime", { detail: message }));
  }
}
