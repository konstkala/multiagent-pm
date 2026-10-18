import { expect, test } from "@playwright/test";

import { EMPLOYEE_STATE, MANAGER_STATE, apiAs, data, unique } from "./helpers";

function inDays(days: number): string {
  const day = new Date();
  day.setDate(day.getDate() + days);
  const month = String(day.getMonth() + 1).padStart(2, "0");
  return `${day.getFullYear()}-${month}-${String(day.getDate()).padStart(2, "0")}`;
}

test.describe("as a manager", () => {
  test.use({ storageState: MANAGER_STATE });

  test("the dashboard shows flow, workload and the AI agents", async ({ page }) => {
    const { projectId, managerName } = data();
    const created = await apiAs(page, "post", `/projects/${projectId}/tickets`, { title: unique("Ship it") });
    await apiAs(page, "patch", `/tickets/${String(created.id)}`, { status: "done" });

    await page.goto(`/projects/${projectId}/dashboard`);
    await expect(page.getByRole("heading", { name: "Created and done per week" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workload" })).toBeVisible();
    await expect(page.getByRole("cell", { name: managerName })).toBeVisible();
    await expect(page.getByRole("heading", { name: "AI agents" })).toBeVisible();
    await page.getByRole("button", { name: "7 days" }).click();
    await expect(page.getByRole("button", { name: "7 days" })).toHaveAttribute("aria-pressed", "true");
  });

  test("the calendar shows a ticket on its due date", async ({ page }) => {
    const { projectId } = data();
    const title = unique("Renew certificates");
    await apiAs(page, "post", `/projects/${projectId}/tickets`, { title, due_date: inDays(0) });

    await page.goto("/calendar");
    await expect(page.getByRole("link", { name: new RegExp(title) })).toBeVisible();
    await page.getByLabel("Only mine").check();
    await expect(page.getByRole("link", { name: new RegExp(title) })).toHaveCount(0); // not assigned to me
  });
});

test.describe("as an employee", () => {
  test.use({ storageState: EMPLOYEE_STATE });

  test("my work lists my tickets; manager-only panels stay hidden", async ({ page, browser }) => {
    const { projectId, employeeId } = data();
    const title = unique("Patch the server");
    const managerContext = await browser.newContext({ storageState: MANAGER_STATE });
    const manager = await managerContext.newPage();
    const created = await apiAs(manager, "post", `/projects/${projectId}/tickets`, {
      title,
      assignee_id: employeeId,
      due_date: inDays(2),
    });
    await managerContext.close();

    await page.goto("/me");
    await expect(page.getByRole("link", { name: new RegExp(title) })).toBeVisible();

    await page.goto(`/projects/${projectId}/tickets/${String(created.id)}`);
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Suggested assignees" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Copy as a new ticket" })).toHaveCount(0);

    await page.goto(`/projects/${projectId}/dashboard`);
    await expect(page.getByRole("heading", { name: "Your workload" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "AI agents" })).toHaveCount(0);
  });
});
