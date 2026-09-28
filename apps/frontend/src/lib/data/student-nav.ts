/**
 * Grouped student navigation (W2). The flat student nav has ten destinations;
 * grouping them by learning journey makes the mental model clearer without
 * changing any route. Used by the mobile drawer's section headers.
 */

export interface StudentNavItem {
  href: string;
  label: string;
  icon: string;
}

export interface StudentNavGroup {
  group: string;
  items: StudentNavItem[];
}

/** Canonical group order for the student area. */
export const STUDENT_NAV_GROUPS: { group: string; hrefs: string[] }[] = [
  { group: "Belajar", hrefs: ["/dashboard", "/learning"] },
  { group: "Kompetisi", hrefs: ["/rooms", "/exams", "/quests", "/tasks", "/ranking"] },
  { group: "Pencapaian", hrefs: ["/badges"] },
  { group: "Karier", hrefs: ["/career", "/assistant"] },
];

/**
 * Group a flat nav list by the canonical journey order.
 *
 * Items not listed in any group (e.g. a future route) are appended under
 * "Lainnya" so the navigation never silently hides a destination.
 */
export function groupStudentNav(items: StudentNavItem[]): StudentNavGroup[] {
  const byHref = new Map(items.map((i) => [i.href, i]));
  const groups: StudentNavGroup[] = [];
  const seen = new Set<string>();

  for (const { group, hrefs } of STUDENT_NAV_GROUPS) {
    const grouped = hrefs
      .map((href) => byHref.get(href))
      .filter((i): i is StudentNavItem => i !== undefined);
    if (grouped.length) {
      groups.push({ group, items: grouped });
      for (const i of grouped) seen.add(i.href);
    }
  }

  const leftover = items.filter((i) => !seen.has(i.href));
  if (leftover.length) groups.push({ group: "Lainnya", items: leftover });
  return groups;
}
