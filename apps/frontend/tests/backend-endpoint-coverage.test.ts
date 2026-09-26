// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import leaderboardsSrc from "$routes-panel/admin/leaderboards/+page.svelte?raw";
import resourcesSrc from "$routes-panel/teacher/resources/+page.svelte?raw";
import assistantSrc from "$routes-site/assistant/+page.svelte?raw";
import teacherConsSrc from "$routes-panel/teacher/consultations/+page.svelte?raw";
import learningSrc from "$routes-site/learning/[courseId]/+page.svelte?raw";
import profileSrc from "$routes-site/profile/+page.svelte?raw";

import adminNotificationsSrc from "$routes-panel/admin/notifications/+page.svelte?raw";
import adminBlockchainSrc from "$routes-panel/admin/blockchain/+page.svelte?raw";

/**
 * Regression for C88 re-audit: endpoints that were backend-only must have a
 * frontend caller so no capability is reachable only via curl.
 */
describe("previously backend-only endpoints now have a UI caller", () => {
  it("admin can broadcast notifications (POST /admin/notifications)", () => {
    expect(adminNotificationsSrc).toContain("/admin/notifications");
    expect(adminNotificationsSrc).toContain("sendBroadcast");
  });

  it("admin sees blockchain contracts and allocations (GET /blockchain/contract and /blockchain/allocations)", () => {
    expect(adminBlockchainSrc).toContain("/blockchain/contract");
    expect(adminBlockchainSrc).toContain("/blockchain/allocations");
  });
  it("admin can open a materialized leaderboard snapshot's entries", () => {
    expect(leaderboardsSrc).toContain("/rankings/leaderboards/${id}/entries");
    expect(leaderboardsSrc).toContain("openEntries");
  });

  it("teacher can edit a resource (PATCH /career/resources/{code})", () => {
    expect(resourcesSrc).toContain("api.patch(`/career/resources/");
    expect(resourcesSrc).toContain("editResource");
  });

  it("student can delete an assistant conversation", () => {
    expect(assistantSrc).toContain("api.delete(`/career/assistant/conversations/");
    expect(assistantSrc).toContain("removeConversation");
  });

  it("teacher can reschedule a consultation", () => {
    expect(teacherConsSrc).toContain("/reschedule");
    expect(teacherConsSrc).toContain("reschedule");
  });

  it("student sees the course progress resume pointer", () => {
    expect(learningSrc).toContain("/progress`");
    expect(learningSrc).toContain("next_lesson_id");
  });

  it("profile completes the email change in-session (confirm endpoint)", () => {
    expect(profileSrc).toContain("/auth/change-email/request");
    expect(profileSrc).toContain("/auth/change-email/confirm");
    expect(profileSrc).toContain("confirmEmailChange");
  });

  it("profile shows follower/following counts via the follow status endpoint", () => {
    expect(profileSrc).toContain("/follow`");
    expect(profileSrc).toContain("followCounts");
  });
});
