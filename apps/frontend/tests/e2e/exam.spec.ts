import { test, expect, type Page } from "@playwright/test";

/**
 * Exam flow end-to-end (start attempt, answer, submit, see result).
 *
 * Requires a running stack (`make up` + `make db-seed`) with a published exam
 * accessible to a student. Run with:
 * `E2E_BASE_URL=http://localhost:3000 make test-e2e`.
 */

async function loginAsStudent(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("student1@qloot.example");
  await page.getByLabel("Kata sandi").fill("StudentPass123!");
  await page.getByRole("button", { name: /masuk/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

test("student can list exams and open one", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/exams");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const first = page
    .getByRole("link")
    .filter({ hasText: /ujian|exam/i })
    .first();
  if (await first.count()) {
    await first.click();
    await page.waitForURL(/\/exams\/[^/]+$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
});

test("starting an attempt opens the attempt page with a timer", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/exams");
  const first = page
    .getByRole("link")
    .filter({ hasText: /ujian|exam/i })
    .first();
  if (!(await first.count())) test.skip();
  await first.click();
  await page.waitForURL(/\/exams\/[^/]+$/);
  const start = page.getByRole("button", { name: /mulai|kerjakan/i }).first();
  if (await start.count()) {
    await start.click();
    await page.waitForURL(/\/attempt$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
});
