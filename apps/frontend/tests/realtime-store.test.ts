// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { get as getStoreValue } from "svelte/store";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  api: {
    get: (...args: unknown[]) => apiGet(...args),
  },
}));

import { opt } from "../src/lib/stores/opt";
import { notifications } from "../src/lib/stores/notifications";
import {
  dispatchRealtimeMessage,
  onRealtime,
  realtimeEvent,
  type RealtimeMessage,
} from "../src/lib/stores/realtime";

describe("realtime store and event dispatcher", () => {
  beforeEach(() => {
    opt.reset();
    apiGet.mockReset();
    realtimeEvent.set({ event: null, timestamp: 0 });
  });

  describe("onRealtime subscription and filtering", () => {
    it("subscribes and receives matching events by string type", () => {
      const received: RealtimeMessage[] = [];
      const unsub = onRealtime("wallet.updated", (msg) => {
        received.push(msg);
      });

      dispatchRealtimeMessage({ type: "wallet.updated", asset: "OPT", balance: 150 });
      dispatchRealtimeMessage({ type: "other.event" });

      expect(received).toHaveLength(1);
      expect(received[0].balance).toBe(150);

      unsub();
      dispatchRealtimeMessage({ type: "wallet.updated", asset: "OPT", balance: 200 });
      expect(received).toHaveLength(1); // not called after unsub
    });

    it("filters notifications by kind shorthand (notification:reward)", () => {
      const received: RealtimeMessage[] = [];
      const unsub = onRealtime("notification:reward", (msg) => {
        received.push(msg);
      });

      dispatchRealtimeMessage({ type: "notification", kind: "reward", title: "Reward earned" });
      dispatchRealtimeMessage({ type: "notification", kind: "system", title: "Maintenance" });
      dispatchRealtimeMessage({ type: "wallet.updated", asset: "OPT" });

      expect(received).toHaveLength(1);
      expect(received[0].title).toBe("Reward earned");

      unsub();
    });

    it("supports array of filters and function predicates", () => {
      const receivedArray: RealtimeMessage[] = [];
      const unsubArray = onRealtime(["wallet.updated", "notification:task"], (msg) => {
        receivedArray.push(msg);
      });

      const receivedFn: RealtimeMessage[] = [];
      const unsubFn = onRealtime(
        (msg) => msg.amount !== undefined && msg.amount > 50,
        (msg) => receivedFn.push(msg),
      );

      dispatchRealtimeMessage({ type: "wallet.updated", amount: 100 });
      dispatchRealtimeMessage({ type: "notification", kind: "task", amount: 20 });
      dispatchRealtimeMessage({ type: "quest.completed", amount: 200 });

      expect(receivedArray).toHaveLength(2);
      expect(receivedFn).toHaveLength(2); // amount 100 and amount 200

      unsubArray();
      unsubFn();
    });

    it("handles listener errors gracefully without blocking other listeners", () => {
      const errListener = () => {
        throw new Error("listener error");
      };
      const okListener = vi.fn();

      const unsubErr = onRealtime("wallet.updated", errListener);
      const unsubOk = onRealtime("wallet.updated", okListener);

      expect(() => {
        dispatchRealtimeMessage({ type: "wallet.updated", asset: "OPT", balance: 50 });
      }).not.toThrow();

      expect(okListener).toHaveBeenCalledTimes(1);

      unsubErr();
      unsubOk();
    });
  });

  describe("dispatchRealtimeMessage store mutations", () => {
    it("updates opt store balance immediately on wallet.updated for OPT", () => {
      expect(getStoreValue(opt).available).toBe(0);

      dispatchRealtimeMessage({
        type: "wallet.updated",
        asset: "OPT",
        balance: 450,
        amount: 50,
      });

      const current = getStoreValue(opt);
      expect(current.available).toBe(450);
      expect(current.loaded).toBe(true);
    });

    it("triggers opt.refresh when notification is a reward or quest", async () => {
      const refreshSpy = vi.spyOn(opt, "refresh").mockResolvedValue(undefined);

      dispatchRealtimeMessage({
        type: "notification",
        kind: "reward",
        title: "Tugas selesai!",
      });

      expect(refreshSpy).toHaveBeenCalled();
      refreshSpy.mockRestore();
    });

    it("triggers opt.refresh on withdrawal.updated", async () => {
      const refreshSpy = vi.spyOn(opt, "refresh").mockResolvedValue(undefined);

      dispatchRealtimeMessage({
        type: "withdrawal.updated",
        id: "w-1",
        status: "completed",
      });

      expect(refreshSpy).toHaveBeenCalled();
      refreshSpy.mockRestore();
    });

    it("dispatches qloot:realtime custom event on window", () => {
      const windowSpy = vi.fn();
      window.addEventListener("qloot:realtime", windowSpy);

      const payload = { type: "task.submitted", id: "t1" };
      dispatchRealtimeMessage(payload);

      expect(windowSpy).toHaveBeenCalled();
      const eventArg = windowSpy.mock.calls[0][0] as CustomEvent;
      expect(eventArg.detail).toEqual(payload);

      window.removeEventListener("qloot:realtime", windowSpy);
    });
  });

  describe("opt store setBalance", () => {
    it("allows updating available and pending balance atomically", () => {
      opt.setBalance(100, 25);
      const state = getStoreValue(opt);
      expect(state.available).toBe(100);
      expect(state.pending).toBe(25);
      expect(state.loaded).toBe(true);
    });
  });
});
