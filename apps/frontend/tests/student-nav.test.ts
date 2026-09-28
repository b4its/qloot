import { describe, it, expect } from "vitest";
import { groupStudentNav, STUDENT_NAV_GROUPS } from "$lib/data/student-nav";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: "gauge-high" },
  { href: "/learning", label: "Pelajaran Saya", icon: "book-open-reader" },
  { href: "/rooms", label: "Ruang", icon: "bullseye" },
  { href: "/exams", label: "Ujian", icon: "file-pen" },
  { href: "/quests", label: "Quest", icon: "trophy" },
  { href: "/tasks", label: "Tugas", icon: "list-check" },
  { href: "/ranking", label: "Peringkat", icon: "ranking-star" },
  { href: "/badges", label: "Badge", icon: "medal" },
  { href: "/career", label: "Karier", icon: "compass" },
  { href: "/assistant", label: "Asisten Qlo", icon: "robot" },
];

describe("student navigation grouping (W2)", () => {
  it("groups every destination under a journey section, losing none", () => {
    const groups = groupStudentNav(nav);
    const flat = groups.flatMap((g) => g.items.map((i) => i.href));
    expect(flat.sort()).toEqual(nav.map((n) => n.href).sort());
    expect(groups.length).toBeGreaterThanOrEqual(4);
  });

  it("orders groups by the canonical learning journey", () => {
    const groups = groupStudentNav(nav);
    expect(groups[0].group).toBe("Belajar");
    expect(groups.map((g) => g.group)).toEqual(STUDENT_NAV_GROUPS.map((g) => g.group));
  });

  it("keeps unknown routes visible under Lainnya instead of hiding them", () => {
    const withExtra = [...nav, { href: "/new-feature", label: "Baru", icon: "star" }];
    const groups = groupStudentNav(withExtra);
    const last = groups.at(-1);
    expect(last?.group).toBe("Lainnya");
    expect(last?.items.map((i) => i.href)).toContain("/new-feature");
  });

  it("omits empty groups", () => {
    const groups = groupStudentNav([{ href: "/badges", label: "Badge", icon: "medal" }]);
    expect(groups).toHaveLength(1);
    expect(groups[0].group).toBe("Pencapaian");
  });
});
