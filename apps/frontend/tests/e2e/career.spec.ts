import { test, expect, type Page } from "@playwright/test";

/**
 * Career guidance end-to-end (assistant, roadmap, library).
 *
 * Requires a running stack (`make up` + `make db-seed`). Run with:
 * `E2E_BASE_URL=http://localhost:3000 make test-e2e`.
 */

async function loginAsStudent(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("student1@qloot.example");
  await page.getByLabel("Kata sandi").fill("StudentPass123!");
  await page.getByRole("button", { name: /masuk/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

test("student can open the career hub and the assistant", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/career");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("assistant answers a question and streams a reply", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/career/assistant");
  const input = page.getByLabel(/pertanyaan untuk asisten/i);
  await input.fill("Apa itu SNBP?");
  await input.press("Enter");
  // A reply is rendered in the live log region.
  await expect(page.getByRole("log")).toContainText(/SNBP|asisten/i, { timeout: 15_000 });
});

test("resource library is searchable", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/career/library");
  await expect(page.getByLabel(/cari sumber daya/i)).toBeVisible();
});
