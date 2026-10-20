import { expect, test } from "@playwright/test";

import { MANAGER_STATE } from "./helpers";

test.describe("signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a stranger sees the landing page and can start from it", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: /Agents prepare/ })).toBeVisible();
    await page.getByRole("link", { name: "Get started" }).first().click();
    await expect(page).toHaveURL(/\/sign-up/);
  });

  test("the protected pages still send a stranger to sign in", async ({ page }) => {
    await page.goto("/projects");
    await expect(page).toHaveURL(/\/sign-in/);
  });
});

test.describe("signed in", () => {
  test.use({ storageState: MANAGER_STATE });

  test("the home page skips straight to the projects", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/projects/);
  });
});
