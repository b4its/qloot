// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import roadmapSrc from "$routes-site/career/roadmap/+page.svelte?raw";

describe("roadmap task checkoff (CARE-05)", () => {
  it("toggles tasks through the per-task endpoint", () => {
    expect(roadmapSrc).toContain("/tasks/");
    expect(roadmapSrc).toContain("/toggle");
  });

  it("no longer uses a hardcoded +25% progress button", () => {
    expect(roadmapSrc).not.toContain("+25%");
    expect(roadmapSrc).not.toContain("progress_percent + 25");
  });

  it("supports adding and reordering milestones", () => {
    expect(roadmapSrc).toContain("/career/roadmap/reorder");
    expect(roadmapSrc).toContain("ordered_ids");
    expect(roadmapSrc).toContain("Tambah tonggak");
  });

  it("lets the student set progress directly", () => {
    expect(roadmapSrc).toContain("setProgress");
  });
});
