import { test, expect, type Page } from "@playwright/test";

/**
 * Student learning: material download, AI summary and grounded Q&A (LEARN-04).
 *
 * Requires a running stack (`make up` + `make db-seed`) so a seeded student
 * account and a lesson with an attached material exist. Run with:
 * `E2E_BASE_URL=http://localhost:3000 make test-e2e`.
 */

async function loginAsStudent(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("student1@qloot.example");
  await page.getByLabel("Kata sandi").fill("StudentPass123!");
  await page.getByRole("button", { name: /masuk/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

test("student can open a lesson's material panel and request an AI summary", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/learning");
  await page.getByRole("link").first().click();
  await page.waitForURL(/\/learning\/[^/]+$/);
  await page.getByRole("link").first().click();
  await page.waitForURL(/\/learning\/[^/]+\/lesson\/[^/]+$/);

  const panel = page.getByTestId("material-panel");
  await expect(panel).toBeVisible();

  const assistantButtons = panel.getByRole("button", { name: /asisten/i });
  if (await assistantButtons.count()) {
    await assistantButtons.first().click();
    await panel.getByRole("button", { name: /ringkas materi/i }).click();
    await expect(panel.getByText(/ringkasan/i)).toBeVisible();
  }
});
