// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import leaderboardsSrc from "$routes-panel/admin/leaderboards/+page.svelte?raw";
import resourcesSrc from "$routes-panel/teacher/resources/+page.svelte?raw";
import assistantSrc from "$routes-site/assistant/+page.svelte?raw";
import teacherConsSrc from "$routes-panel/teacher/consultations/+page.svelte?raw";
import learningSrc from "$routes-site/learning/[courseId]/+page.svelte?raw";

/**
 * Regression for C88 re-audit: endpoints that were backend-only must have a
 * frontend caller so no capability is reachable only via curl.
 */
describe("previously backend-only endpoints now have a UI caller", () => {
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
});
