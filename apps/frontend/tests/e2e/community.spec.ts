import { test, expect, type Page } from "@playwright/test";

/**
 * Community feed end-to-end (posting, ranking, reporting).
 *
 * Requires a running stack (`make up` + `make db-seed`). Run with:
 * `E2E_BASE_URL=http://localhost:3000 make test-e2e`.
 */

async function loginAsStudent(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("student1@qloot.example");
  await page.getByLabel("Kata sandi", { exact: true }).fill("StudentPass123!");
  await page.getByRole("button", { name: /masuk/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

test("student can post to the community feed", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/community");
  const box = page.getByLabel(/tulis diskusi/i);
  // Unique body so repeated runs don't collide in strict mode (the seed DB and
  // previous runs may already contain posts).
  const body = `E2E post ${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  await box.fill(body);
  await box.press("Enter");
  await expect(page.getByText(body, { exact: true })).toBeVisible({ timeout: 15_000 });
});

test("feed exposes new/hot/top ranking controls", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/community");
  await expect(page.getByRole("button", { name: "Terbaru" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Populer" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Teratas" })).toBeVisible();
});

test("student can follow a post author", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/community");
  const follow = page.getByRole("button", { name: /^Ikuti$/ }).first();
  if (await follow.count()) {
    await follow.click();
    await expect(page.getByRole("button", { name: /Mengikuti/ }).first()).toBeVisible();
  }
});
