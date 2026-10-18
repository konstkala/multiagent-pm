import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { test as setup } from "@playwright/test";

import {
  DATA_FILE,
  EMPLOYEE_STATE,
  MANAGER_STATE,
  apiAs,
  resetSignupLimits,
  signIn,
  signUpViaApi,
  uniqueEmail,
  type E2EData,
} from "./helpers";

setup("sign in a manager and an employee, with a shared project", async ({ browser, request }) => {
  resetSignupLimits();
  const managerEmail = uniqueEmail("e2e-manager");
  const employeeEmail = uniqueEmail("e2e-employee");
  await signUpViaApi(request, managerEmail, "Mia Manager");
  await signUpViaApi(request, employeeEmail, "Eli Employee");

  const manager = await browser.newContext();
  const managerPage = await manager.newPage();
  await signIn(managerPage, managerEmail);
  const workspace = await apiAs(managerPage, "post", "/workspaces", { name: "E2E" });
  const project = await apiAs(managerPage, "post", `/workspaces/${String(workspace.id)}/projects`, {
    key: "E2E",
    name: "Browser tests",
  });
  const member = await apiAs(managerPage, "post", `/projects/${String(project.id)}/members`, {
    email: employeeEmail,
    role: "employee",
  });

  const employee = await browser.newContext();
  const employeePage = await employee.newPage();
  await signIn(employeePage, employeeEmail);

  mkdirSync(path.dirname(MANAGER_STATE), { recursive: true });
  await manager.storageState({ path: MANAGER_STATE });
  await employee.storageState({ path: EMPLOYEE_STATE });
  const shared: E2EData = {
    projectId: String(project.id),
    projectKey: "E2E",
    managerName: "Mia Manager",
    employeeId: String(member.user_id),
    employeeName: "Eli Employee",
  };
  writeFileSync(DATA_FILE, JSON.stringify(shared));
  await manager.close();
  await employee.close();
});
