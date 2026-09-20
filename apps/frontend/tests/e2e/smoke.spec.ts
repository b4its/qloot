import { test, expect } from "@playwright/test";

/**
 * Requires a running stack: `make up` (backend on :8000, frontend on :3000).
 * Run with: `E2E_BASE_URL=http://localhost:3000 make test-e2e`
 */

test("landing page renders and links to auth", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("didampingi");
  await expect(page.getByRole("link", { name: "Masuk" }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Daftar" }).first()).toBeVisible();
});

test("landing page is a one-page experience with anchor nav", async ({ page }) => {
  await page.goto("/");
  // Every in-page anchor target must exist on the landing page itself.
  for (const id of ["fitur", "kelas", "guru", "sertifikat", "testimoni"]) {
    await expect(page.locator(`#${id}`)).toHaveCount(1);
  }
  await expect(page.getByRole("button", { name: "Fitur" })).toBeVisible();
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

test("register then reach dashboard", async ({ page }) => {
  const email = `e2e_${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Nama lengkap").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Kata sandi").fill("Password123!");
  await page.getByRole("button", { name: /daftar/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Halo");
});
