// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";

// Components only import the Icon wrapper (no network).
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import PageHeader from "$lib/components/PageHeader.svelte";
import PageAlerts from "$lib/components/PageAlerts.svelte";
import { adminNav, teacherNav } from "$lib/data/role-nav";

describe("PageHeader", () => {
  beforeEach(() => cleanup());

  it("renders the eyebrow, title and subtitle", () => {
    render(PageHeader, {
      eyebrow: "Panel Guru · Pelajaran",
      title: "Pelajaran",
      subtitle: "Kelola pelajaran",
    });
    expect(screen.getByText("Panel Guru · Pelajaran")).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("Pelajaran");
    expect(screen.getByText("Kelola pelajaran")).toBeTruthy();
  });

  it("renders a back link when backHref is set", () => {
    render(PageHeader, {
      eyebrow: "Admin",
      title: "Pengguna",
      backHref: "/admin",
      backLabel: "Admin",
    });
    const back = screen.getByRole("link", { name: /admin/i });
    expect(back.getAttribute("href")).toBe("/admin");
  });

  it("renders a primary action link when provided", () => {
    render(PageHeader, {
      eyebrow: "Admin",
      title: "Pengguna",
      actionHref: "/admin/users/new",
      actionLabel: "Tambah pengguna",
    });
    const action = screen.getByRole("link", { name: /tambah pengguna/i });
    expect(action.getAttribute("href")).toBe("/admin/users/new");
  });

  it("renders no links when neither back nor action is given", () => {
    const { container } = render(PageHeader, { eyebrow: "X", title: "Y" });
    expect(container.querySelectorAll("a").length).toBe(0);
  });
});

describe("PageAlerts", () => {
  beforeEach(() => cleanup());

  it("renders nothing when empty", () => {
    const { container } = render(PageAlerts, { message: "", error: "" });
    expect(container.querySelector(".alert-ok")).toBeNull();
    expect(container.querySelector(".alert-error")).toBeNull();
  });

  it("renders the success and error banners", () => {
    render(PageAlerts, { message: "Tersimpan", error: "Gagal" });
    expect(screen.getByText("Tersimpan")).toBeTruthy();
    expect(screen.getByText("Gagal")).toBeTruthy();
  });
});

describe("role-nav config", () => {
  it("keeps teacher and admin sections distinct and non-empty", () => {
    const teacherHrefs = teacherNav.map((n) => n.href);
    const adminHrefs = adminNav.map((n) => n.href);

    expect(teacherHrefs).toContain("/teacher/subjects");
    expect(teacherHrefs.every((h) => h.startsWith("/teacher"))).toBe(true);
    expect(adminHrefs).toContain("/admin/users");
    expect(adminHrefs.every((h) => h.startsWith("/admin"))).toBe(true);

    // No overlap: teacher and admin areas never share a route prefix.
    expect(teacherHrefs.some((h) => adminHrefs.includes(h))).toBe(false);
    expect(teacherHrefs[0]).toBe("/teacher");
    expect(adminHrefs[0]).toBe("/admin");
  });
});
