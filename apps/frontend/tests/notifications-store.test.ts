// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { get as getStoreValue } from "svelte/store";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  api: { get: (...args: unknown[]) => apiGet(...args) },
}));

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }

  close() {}
}

vi.stubGlobal("WebSocket", MockWebSocket);

import { notifications } from "../src/lib/stores/notifications";

describe("notification store reliability", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    notifications.clear();
    apiGet.mockReset();
    MockWebSocket.instances = [];
  });

  afterEach(() => {
    notifications.clear();
    vi.useRealTimers();
  });

  it("preserves the last unread count when refresh fails", async () => {
    apiGet.mockResolvedValueOnce({ unread: 7 });
    await notifications.refresh();
    apiGet.mockRejectedValueOnce(new Error("network unavailable"));

    await notifications.refresh();

    expect(getStoreValue(notifications)).toBe(7);
  });

  it("reconnects with exponential delays capped at 30 seconds", async () => {
    apiGet.mockResolvedValue({ unread: 2 });
    notifications.start();
    expect(MockWebSocket.instances).toHaveLength(1);

    MockWebSocket.instances[0].onclose?.();
    await vi.advanceTimersByTimeAsync(999);
    expect(MockWebSocket.instances).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(MockWebSocket.instances).toHaveLength(2);

    for (const delay of [2_000, 4_000, 8_000, 16_000, 30_000, 30_000]) {
      MockWebSocket.instances.at(-1)?.onclose?.();
      await vi.advanceTimersByTimeAsync(delay - 1);
      const count = MockWebSocket.instances.length;
      await vi.advanceTimersByTimeAsync(1);
      expect(MockWebSocket.instances).toHaveLength(count + 1);
    }
  });

  it("cancels a pending reconnect when stopped", async () => {
    apiGet.mockResolvedValue({ unread: 0 });
    notifications.start();
    MockWebSocket.instances[0].onclose?.();

    notifications.stop();
    await vi.advanceTimersByTimeAsync(30_000);

    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
