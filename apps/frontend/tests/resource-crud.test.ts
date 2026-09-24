// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { teacherNav } from "$lib/data/role-nav";
import librarySrc from "$routes-site/career/library/+page.svelte?raw";
import teacherSrc from "$routes-panel/teacher/resources/+page.svelte?raw";

describe("resource search and CRUD (CARE-07)", () => {
  it("student library supports free-text search", () => {
    expect(librarySrc).toContain('qs.set("q"');
    expect(librarySrc).toContain("Cari sumber daya");
  });

  it("teacher panel is linked from the nav", () => {
    expect(teacherNav.some((n) => n.href === "/teacher/resources")).toBe(true);
  });

  it("teacher panel calls create and delete endpoints", () => {
    expect(teacherSrc).toContain('api.post("/career/resources"');
    expect(teacherSrc).toContain("/career/resources/");
    expect(teacherSrc).toContain("api.delete");
  });
});
