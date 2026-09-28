// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import learningSrc from "$routes-site/learning/+page.svelte?raw";
import dashboardSrc from "$routes-site/dashboard/+page.svelte?raw";

describe("learning progress accessibility", () => {
  it("exposes course-card progress with lesson-based values", () => {
    expect(learningSrc).toContain("aria-label={`Progres ${course.title}`}");
    expect(learningSrc).toContain("aria-valuemax={total}");
    expect(learningSrc).toContain("aria-valuenow={done}");
  });

  it("labels dashboard interest and personality dimensions as progress values", () => {
    expect(dashboardSrc).toContain("aria-label={`Nilai minat ${dim.dimension}`}");
    expect(dashboardSrc).toContain("aria-label={`Nilai kepribadian ${t.l}`}");
    expect(dashboardSrc).toContain("aria-valuemax={100}");
  });
});
