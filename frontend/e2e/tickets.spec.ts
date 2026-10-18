import { expect, test } from "@playwright/test";

import { MANAGER_STATE, apiAs, data, unique } from "./helpers";

test.use({ storageState: MANAGER_STATE });

// A real PNG header: the API checks file content, not the name.
const PNG = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(64)]);

test("a manager creates a ticket, edits it, comments and attaches a file", async ({ page }) => {
  const { projectId, employeeName } = data();
  const title = unique("Login page returns 500");

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("button", { name: "New ticket" }).click();
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Story points").selectOption("3");
  await page.getByRole("button", { name: "Create ticket" }).click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();

  await page.getByLabel("Status", { exact: true }).selectOption("in_progress");
  await expect(page.getByLabel("Status", { exact: true })).toHaveValue("in_progress");
  // Next.js keeps the previous page mounted but hidden (instant back), so match visible only.
  const assignee = page.getByLabel("Assignee", { exact: true }).filter({ visible: true });
  await assignee.selectOption({ label: employeeName });
  await expect(assignee).toHaveValue(/.+/);

  const renamed = `${title} (renamed)`;
  await page.getByRole("heading", { level: 1 }).getByRole("button", { name: "Edit" }).click();
  const titleBox = page.getByLabel("Title").filter({ visible: true });
  await titleBox.fill(renamed);
  await titleBox.press("Enter");
  await expect(page.getByRole("heading", { level: 1, name: renamed })).toBeVisible();

  await page.getByPlaceholder("Add a comment…").fill("Looking into it now.");
  await page.getByRole("button", { name: "Comment", exact: true }).click();
  await expect(page.getByText("Looking into it now.")).toBeVisible();

  await page.getByLabel("Attach a file").setInputFiles({ name: "screenshot.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByRole("link", { name: "screenshot.png" })).toBeVisible();

  await expect(page.getByRole("heading", { name: "AI triage" })).toBeVisible();
});

test("the list filters by status and searches", async ({ page }) => {
  const { projectId } = data();
  const title = unique("Searchable ticket");
  const created = await apiAs(page, "post", `/projects/${projectId}/tickets`, { title });

  await page.goto(`/projects/${projectId}`);
  await page.getByLabel("Search").fill(title);
  await expect(page.getByRole("link", { name: title })).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(2); // header + our ticket

  await page.getByRole("button", { name: "Done", exact: true }).click(); // status filter chip
  await expect(page.getByText("No tickets match these filters.")).toBeVisible();
  expect(created.status).toBe("todo");
});

test("a card dragged on the board changes status", async ({ page }) => {
  const { projectId } = data();
  const title = unique("Drag me");
  const created = await apiAs(page, "post", `/projects/${projectId}/tickets`, { title });

  await page.goto(`/projects/${projectId}/board`);
  // dnd-kit gives draggable cards role="button", so find the card by its tag.
  const card = page.locator("article").filter({ hasText: title });
  const target = page.getByRole("region", { name: "In progress" });
  // The card's drag handle is a button named "Move KEY-n".
  const handle = await card.getByRole("button", { name: /^Move / }).boundingBox();
  const drop = await target.boundingBox();
  if (!handle || !drop) throw new Error("board not laid out");
  await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
  await page.mouse.down();
  await page.mouse.move(drop.x + drop.width / 2, drop.y + drop.height / 2, { steps: 15 });
  await page.mouse.up();

  await expect(target.getByText(title)).toBeVisible();
  await expect
    .poll(async () => (await apiAs(page, "get", `/tickets/${String(created.id)}`)).status)
    .toBe("in_progress");
});
