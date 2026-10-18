import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, request, type APIRequestContext, type Page } from "@playwright/test";

export const PASSWORD = "correct horse battery";
export const CSRF = { "x-requested-with": "fetch" }; // the API's CSRF guard
const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025/api/v1";
const AUTH_DIR = path.join(__dirname, ".auth");

export const MANAGER_STATE = path.join(AUTH_DIR, "manager.json");
export const EMPLOYEE_STATE = path.join(AUTH_DIR, "employee.json");
export const DATA_FILE = path.join(AUTH_DIR, "data.json");

/** What the setup step created, shared with every test. */
export type E2EData = {
  projectId: string;
  projectKey: string;
  managerName: string;
  employeeId: string;
  employeeName: string;
};

export function data(): E2EData {
  return JSON.parse(readFileSync(DATA_FILE, "utf-8")) as E2EData;
}

export function uniqueEmail(name: string): string {
  return `${name}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
}

export function unique(text: string): string {
  return `${text} ${Date.now().toString(36)}`;
}

/** The token from the newest email to `email` whose subject contains `subject`. */
export async function emailToken(email: string, subject: string): Promise<string> {
  const mailpit = await request.newContext();
  try {
    for (let attempt = 0; attempt < 40; attempt++) {
      const found = (await (await mailpit.get(`${MAILPIT}/search`, { params: { query: `to:${email}` } })).json()) as {
        messages: { ID: string; Subject: string }[];
      };
      const message = found.messages.find((m) => m.Subject.includes(subject));
      if (message) {
        const { Text } = (await (await mailpit.get(`${MAILPIT}/message/${message.ID}`)).json()) as { Text: string };
        const token = /token=([\w-]+)/.exec(Text)?.[1];
        if (token) return token;
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  } finally {
    await mailpit.dispose();
  }
  throw new Error(`No "${subject}" email for ${email}`);
}

/** Creates a confirmed account through the API (arrange via API, act via the UI). */
export async function signUpViaApi(api: APIRequestContext, email: string, name: string): Promise<void> {
  const signUp = await api.post("/api/auth/sign-up", {
    headers: CSRF,
    data: { email, password: PASSWORD, display_name: name },
  });
  expect(signUp.ok(), await signUp.text()).toBeTruthy();
  const token = await emailToken(email, "Confirm");
  const verified = await api.post("/api/auth/verify-email", { headers: CSRF, data: { token } });
  expect(verified.ok(), await verified.text()).toBeTruthy();
}

export async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
}

/** Calls the API as whoever `page` is signed in as (the browser's session cookie). */
export async function apiAs(page: Page, method: "get" | "post" | "patch", url: string, body?: unknown) {
  const response = await page.request[method](`/api${url}`, { headers: CSRF, data: body });
  expect(response.ok(), `${method.toUpperCase()} ${url}: ${await response.text()}`).toBeTruthy();
  return (await response.json()) as Record<string, unknown>;
}

/** Each run signs up several accounts; the limit is 10 per hour per IP. Local stack only. */
export function resetSignupLimits(): void {
  try {
    execSync(
      `docker compose exec -T db psql -U pm -d pm -qc "DELETE FROM rate_limit_buckets WHERE key LIKE 'sign_up:ip:%'"`,
      { stdio: "ignore" },
    );
  } catch {
    // No Docker here (tests against another stack): the limit may apply, which is fine.
  }
}
