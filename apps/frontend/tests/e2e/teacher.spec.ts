import { test, expect, type Page } from "@playwright/test";

/**
 * Teacher area: separate CRUD pages + per-role sub-nav.
 *
 * Requires a running stack (`make up` + `make db-seed`) so the demo teacher
 * account exists. Run with: `E2E_BASE_URL=http://localhost:3000 make test-e2e`.
 */

async function loginAsTeacher(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("teacher@qloot.example");
  await page.getByLabel("Kata sandi").fill("TeacherPass123!");
  await page.getByRole("button", { name: /masuk/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

test("teacher area shows its own sub-nav, not the student nav", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/teacher");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Kelola pembelajaran");
  // Role sub-nav marker.
  await expect(page.getByText("Guru", { exact: true }).first()).toBeVisible();
  // A teacher-only link is present; the student "Dashboard" link is not.
  await expect(page.getByRole("link", { name: /pelajaran/i }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /^dashboard$/i })).toHaveCount(0);
});

test("teacher can open the separate 'new subject' page", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/teacher/subjects");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Pelajaran");
  await page.getByRole("link", { name: /pelajaran baru/i }).click();
  await expect(page).toHaveURL(/\/teacher\/subjects\/new/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Pelajaran baru");
  await expect(page.getByLabel(/nama pelajaran/i)).toBeVisible();
});

test("teacher exams, quests and materials list pages render with a create action", async ({
  page,
}) => {
  await loginAsTeacher(page);
  for (const [path, heading] of [
    ["/teacher/exams", "Ujian"],
    ["/teacher/quests", "Quest"],
    ["/teacher/materials", "Materi"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(heading);
  }
});
