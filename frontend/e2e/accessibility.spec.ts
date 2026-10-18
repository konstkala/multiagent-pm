import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { MANAGER_STATE, apiAs, data, unique } from "./helpers";

// Automated checks catch roughly a third of accessibility problems (contrast, names, labels,
// landmarks). They don't replace trying the keyboard and a screen reader, but they catch
// regressions for free.
test.use({ storageState: MANAGER_STATE });

async function violations(page: Page) {
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);
}

for (const scheme of ["light", "dark"] as const) {
  test(`main pages have no serious accessibility problems (${scheme})`, async ({ page }) => {
    const { projectId } = data();
    await page.emulateMedia({ colorScheme: scheme });
    const created = await apiAs(page, "post", `/projects/${projectId}/tickets`, {
      title: unique("Accessible ticket"),
      due_date: new Date().toISOString().slice(0, 10),
    });
    const paths = [
      "/projects",
      `/projects/${projectId}`,
      `/projects/${projectId}/board`,
      `/projects/${projectId}/tickets/${String(created.id)}`,
      `/projects/${projectId}/dashboard`,
      `/projects/${projectId}/team`,
      "/me",
      "/calendar",
    ];
    const problems: string[] = [];
    for (const path of paths) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500); // colour transitions settle (contrast is measured on the result)
      problems.push(...(await violations(page)).map((v) => `${path}: ${v}`));
    }
    expect(problems).toEqual([]);
  });
}
