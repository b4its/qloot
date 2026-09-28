import { describe, it, expect } from "vitest";
import type { Notification } from "$lib/types";
import { notificationLink } from "$lib/utils/notification-link";

function notification(kind: string, data: Record<string, unknown>): Notification {
  return {
    id: "n1",
    kind,
    title: "Notification",
    data,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("notificationLink", () => {
  it("links a graded exam directly to the exact attempt result", () => {
    expect(notificationLink(notification("reward", { exam_id: "e/1", attempt_id: "a?2" }))).toBe(
      "/exams/e%2F1/result?attempt=a%3F2",
    );
  });

  it.each([
    ["room", { room_id: "r1" }, "/rooms/r1"],
    ["community", { post_id: "p1" }, "/community#post-p1"],
    ["quest", { quest_id: "q1" }, "/quests#quest-q1"],
    ["reward", { task_id: "t1" }, "/tasks#task-t1"],
    ["badge", { code: "xp_500" }, "/badges#badge-xp_500"],
    ["certificate", { credential_id: "cred-1" }, "/verify/cred-1"],
    ["system", { career_destination: "consultation" }, "/career/consultation"],
  ])("resolves %s context to a precise destination", (kind, data, expected) => {
    expect(notificationLink(notification(kind as string, data as Record<string, unknown>))).toBe(
      expected,
    );
  });

  it("uses safe feature fallbacks and rejects arbitrary system destinations", () => {
    expect(notificationLink(notification("reward", {}))).toBe("/wallet");
    expect(
      notificationLink(notification("system", { career_destination: "https://evil.invalid" })),
    ).toBeNull();
  });
});
