// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import dashboardSrc from "$routes-site/dashboard/+page.svelte?raw";

describe("dashboard grade edit and delete (UIX-05)", () => {
  it("offers an edit control that PUTs the grade", () => {
    expect(dashboardSrc).toContain("editGrade");
    expect(dashboardSrc).toContain("api.put(`/career/grades/");
  });

  it("offers a delete control that DELETEs the grade", () => {
    expect(dashboardSrc).toContain("deleteGrade");
    expect(dashboardSrc).toContain("api.delete(`/career/grades/");
  });
});
