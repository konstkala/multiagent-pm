import { expect, test } from "@playwright/test";

import { PASSWORD, emailToken, resetSignupLimits, uniqueEmail } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } }); // a stranger, signed out

test("someone signs up, confirms the email, signs in and out", async ({ page }) => {
  resetSignupLimits();
  const email = uniqueEmail("e2e-new");

  await page.goto("/sign-up");
  await page.getByLabel("Your name").fill("Nia Newcomer");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Check your inbox" })).toBeVisible();

  await page.goto(`/verify-email?token=${await emailToken(email, "Confirm")}`);
  await page.getByRole("button", { name: "Confirm my email address" }).click();
  await expect(page.getByText("Email confirmed. You can sign in now.")).toBeVisible();

  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Create your workspace" })).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/sign-in/);
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/sign-in/); // the session is really gone
});

test("a wrong password is refused", async ({ page }) => {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill("nobody@example.com");
  await page.getByLabel("Password", { exact: true }).fill("not the password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/sign-in/);
});
