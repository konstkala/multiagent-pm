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

// The landing page and the sign-in screens are the first thing a stranger sees: white and mint
// text on the navy hero, green buttons, text over gradients. Checked signed out, both themes.
test.describe("public pages", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  for (const scheme of ["light", "dark"] as const) {
    test(`landing and sign-in pages have no serious accessibility problems (${scheme})`, async ({
      page,
    }) => {
      // Reduced motion shows every section at once: the scroll-reveal would otherwise leave the
      // sections below the fold transparent, and contrast can't be measured on invisible text.
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      const problems: string[] = [];
      for (const path of ["/", "/sign-in", "/sign-up", "/forgot-password"]) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        problems.push(...(await violations(page)).map((v) => `${path}: ${v}`));
      }
      expect(problems).toEqual([]);
    });
  }
});

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
