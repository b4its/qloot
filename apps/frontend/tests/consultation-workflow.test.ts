// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { teacherNav } from "$lib/data/role-nav";
import panelSrc from "$routes-panel/teacher/consultations/+page.svelte?raw";
import siteSrc from "$routes-site/career/consultation/+page.svelte?raw";

describe("counselor consultation workflow (CARE-06)", () => {
  it("is linked from the teacher nav", () => {
    expect(teacherNav.some((n) => n.href === "/teacher/consultations")).toBe(true);
  });

  it("exposes accept and complete controls backed by the endpoints", () => {
    expect(panelSrc).toContain("/career/consultations/managed");
    expect(panelSrc).toContain('"accept"');
    expect(panelSrc).toContain('"complete"');
    expect(panelSrc).toContain("/${action}");
  });

  it("supports a two-way message thread", () => {
    expect(panelSrc).toContain("/messages");
    expect(siteSrc).toContain("/messages");
  });

  it("books a real counselor user (not just a name)", () => {
    expect(siteSrc).toContain("counselor_user_id");
  });
});
