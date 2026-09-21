import { test, expect, type Page } from "@playwright/test";

/**
 * Admin area: separate CRUD pages + per-role sub-nav.
 *
 * Requires a running stack (`make up` + `make db-seed`) so the demo admin
 * account exists. Run with: `E2E_BASE_URL=http://localhost:3000 make test-e2e`.
 */

async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@qloot.example");
  await page.getByLabel("Kata sandi").fill("AdminPass123!");
  await page.getByRole("button", { name: /masuk/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

test("admin area shows its own sub-nav, not the student nav", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Operasional");
  await expect(page.getByText("Admin", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /pengguna/i }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /^dashboard$/i })).toHaveCount(0);
});

test("admin can open the separate 'new user' page", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Pengguna");
  await page.getByRole("link", { name: /tambah pengguna/i }).click();
  await expect(page).toHaveURL(/\/admin\/users\/new/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Tambah pengguna");
  await expect(page.getByLabel(/nama lengkap/i)).toBeVisible();
});

test("admin blockchain area splits status from transactions/events", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/blockchain");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Blockchain");

  await page
    .getByRole("link", { name: /transaksi/i })
    .first()
    .click();
  await expect(page).toHaveURL(/\/admin\/blockchain\/transactions/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Transaksi");

  await page.goto("/admin/blockchain/events");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Event");
});
