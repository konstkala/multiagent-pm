import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** Typed client generated from the backend's OpenAPI schema (`npm run gen:api`). */
export const api = createClient<paths>({
  // Same origin: next.config.ts proxies /api to FastAPI, so the session cookie is first-party.
  baseUrl: "/api",
  credentials: "same-origin",
  // The backend's CSRF guard requires this header on state-changing requests.
  headers: { "X-Requested-With": "fetch" },
});

export type Schemas = components["schemas"];
export type User = Schemas["UserRead"];
export type Workspace = Schemas["WorkspaceRead"];
export type Project = Schemas["ProjectRead"];
export type Member = Schemas["MemberRead"];
export type Ticket = Schemas["TicketRead"];
export type Invitation = Schemas["InvitationRead"];
export type Person = Schemas["PersonRead"];
export type Profile = Schemas["ProfileRead"];
export type CvImport = Schemas["CvImportRead"];
export type TriageRun = Schemas["TriageRunRead"];

/** An error response from the API, in its one standard shape. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | undefined,
    message: string,
  ) {
    super(message);
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Returns the body, or throws ApiError so callers (and TanStack Query) see one error type. */
export async function call<T>(request: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok) throw toApiError(response.status, error);
  if (data === undefined) throw new ApiError(response.status, undefined, "Empty response");
  return data;
}

/** For endpoints that answer 204 No Content. */
export async function send(request: Promise<Result<unknown>>): Promise<void> {
  const { error, response } = await request;
  if (!response.ok) throw toApiError(response.status, error);
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "Can't reach the server. Check your connection and try again.";
  return "Something went wrong. Try again.";
}

function toApiError(status: number, body: unknown): ApiError {
  if (typeof body === "object" && body !== null && "error" in body) {
    const inner = body.error;
    if (typeof inner === "object" && inner !== null && "code" in inner && "message" in inner) {
      return new ApiError(status, String(inner.code), String(inner.message));
    }
  }
  return new ApiError(status, undefined, "Something went wrong. Try again.");
}
