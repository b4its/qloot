import { test, expect } from "@playwright/test";

/**
 * Requires a running stack: `make up` (backend on :8000, frontend on :3000).
 * Run with: `E2E_BASE_URL=http://localhost:3000 make test-e2e`
 */

test("landing page renders and links to auth", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Learn.");
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toBeVisible();
});

test("theme toggle persists across reload", async ({ page }) => {
  await page.goto("/");
  const html = page.locator("html");
  const before = await html.getAttribute("class");
  await page.getByRole("button", { name: /theme/i }).click();
  const after = await html.getAttribute("class");
  expect(after).not.toBe(before);

  await page.reload();
  const persisted = await html.getAttribute("class");
  expect(persisted).toBe(after);
});

test("register then reach learning page", async ({ page }) => {
  const email = `e2e_${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Full name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("Password123!");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/learning/);
  await expect(page.getByRole("heading", { name: "Learning" })).toBeVisible();
});
