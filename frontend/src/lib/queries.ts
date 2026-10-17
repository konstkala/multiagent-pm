"use client";

import { useQuery } from "@tanstack/react-query";

import { api, call } from "@/lib/api/client";
import type { Category, Status } from "@/lib/tickets";

export type TicketFilters = {
  status?: Status[];
  assignee_id?: string;
  unassigned?: boolean;
  category?: Category;
  label?: string;
  q?: string;
  parent_id?: string;
  limit?: number;
  offset?: number;
};

/** Query keys in one place, so mutations invalidate exactly what they change. */
export const keys = {
  me: ["me"] as const,
  workspaces: ["workspaces"] as const,
  projects: (workspaceId: string) => ["workspaces", workspaceId, "projects"] as const,
  project: (projectId: string) => ["projects", projectId] as const,
  members: (projectId: string) => ["projects", projectId, "members"] as const,
  // Prefix for every ticket list of a project: invalidating it refreshes list, board and sub-tasks.
  ticketLists: (projectId: string) => ["projects", projectId, "tickets"] as const,
  tickets: (projectId: string, filters: TicketFilters) =>
    ["projects", projectId, "tickets", filters] as const,
  ticket: (ticketId: string) => ["tickets", ticketId] as const,
  comments: (ticketId: string) => ["tickets", ticketId, "comments"] as const,
  attachments: (ticketId: string) => ["tickets", ticketId, "attachments"] as const,
  links: (ticketId: string) => ["tickets", ticketId, "links"] as const,
  similar: (ticketId: string) => ["tickets", ticketId, "similar"] as const,
  triage: (ticketId: string) => ["tickets", ticketId, "triage"] as const,
  assignment: (ticketId: string) => ["tickets", ticketId, "assignment"] as const,
};

export function useMe() {
  return useQuery({ queryKey: keys.me, queryFn: () => call(api.GET("/auth/me")) });
}

export function useWorkspaces() {
  return useQuery({ queryKey: keys.workspaces, queryFn: () => call(api.GET("/workspaces")) });
}

export function useProjects(workspaceId: string) {
  return useQuery({
    queryKey: keys.projects(workspaceId),
    queryFn: () =>
      call(
        api.GET("/workspaces/{workspace_id}/projects", {
          params: { path: { workspace_id: workspaceId } },
        }),
      ),
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: keys.project(projectId),
    queryFn: () =>
      call(api.GET("/projects/{project_id}", { params: { path: { project_id: projectId } } })),
  });
}

export function useMembers(projectId: string) {
  return useQuery({
    queryKey: keys.members(projectId),
    queryFn: () =>
      call(
        api.GET("/projects/{project_id}/members", { params: { path: { project_id: projectId } } }),
      ),
  });
}

export function useTickets(projectId: string, filters: TicketFilters = {}) {
  return useQuery({
    queryKey: keys.tickets(projectId, filters),
    queryFn: () =>
      call(
        api.GET("/projects/{project_id}/tickets", {
          params: { path: { project_id: projectId }, query: filters },
        }),
      ),
  });
}

export function useTicket(ticketId: string) {
  return useQuery({
    queryKey: keys.ticket(ticketId),
    queryFn: () =>
      call(api.GET("/tickets/{ticket_id}", { params: { path: { ticket_id: ticketId } } })),
  });
}

export function useComments(ticketId: string) {
  return useQuery({
    queryKey: keys.comments(ticketId),
    queryFn: () =>
      call(api.GET("/tickets/{ticket_id}/comments", { params: { path: { ticket_id: ticketId } } })),
  });
}

export function useAttachments(ticketId: string) {
  return useQuery({
    queryKey: keys.attachments(ticketId),
    queryFn: () =>
      call(
        api.GET("/tickets/{ticket_id}/attachments", { params: { path: { ticket_id: ticketId } } }),
      ),
  });
}

export function useLinks(ticketId: string) {
  return useQuery({
    queryKey: keys.links(ticketId),
    queryFn: () =>
      call(api.GET("/tickets/{ticket_id}/links", { params: { path: { ticket_id: ticketId } } })),
  });
}

export function useSimilar(ticketId: string) {
  return useQuery({
    queryKey: keys.similar(ticketId),
    queryFn: () =>
      call(
        api.GET("/tickets/{ticket_id}/similar", {
          params: { path: { ticket_id: ticketId }, query: { limit: 3 } },
        }),
      ),
    retry: false, // 409 just means "no embedding yet"
  });
}

/** The latest triage run, or null. Polls every 2 s while the agent works. */
export function useTriage(ticketId: string) {
  return useQuery({
    queryKey: keys.triage(ticketId),
    queryFn: () =>
      call(api.GET("/tickets/{ticket_id}/triage", { params: { path: { ticket_id: ticketId } } })),
    refetchInterval: (query) => (query.state.data?.status === "queued" ? 2000 : false),
  });
}

/** Managers only. The latest suggestion run, or null. Polls every 2 s while reasons are written. */
export function useAssignmentSuggestions(ticketId: string) {
  return useQuery({
    queryKey: keys.assignment(ticketId),
    queryFn: () =>
      call(
        api.GET("/tickets/{ticket_id}/assignment-suggestions", {
          params: { path: { ticket_id: ticketId } },
        }),
      ),
    refetchInterval: (query) => (query.state.data?.status === "explaining" ? 2000 : false),
  });
}

export const peopleKeys = {
  invitations: (projectId: string) => ["projects", projectId, "invitations"] as const,
  people: (workspaceId: string) => ["workspaces", workspaceId, "people"] as const,
  profile: (workspaceId: string, userId: string) =>
    ["workspaces", workspaceId, "people", userId] as const,
  imports: (workspaceId: string) => ["workspaces", workspaceId, "cv-imports"] as const,
};

export function useInvitations(projectId: string, enabled: boolean) {
  return useQuery({
    queryKey: peopleKeys.invitations(projectId),
    queryFn: () =>
      call(
        api.GET("/projects/{project_id}/invitations", {
          params: { path: { project_id: projectId } },
        }),
      ),
    enabled, // managers only
  });
}

/** Succeeds only for people managers, so it doubles as the "can I manage people?" check. */
export function usePeople(workspaceId: string) {
  return useQuery({
    queryKey: peopleKeys.people(workspaceId),
    queryFn: () =>
      call(
        api.GET("/workspaces/{workspace_id}/people", {
          params: { path: { workspace_id: workspaceId } },
        }),
      ),
    retry: false,
  });
}

export function useProfile(workspaceId: string, userId: string) {
  return useQuery({
    queryKey: peopleKeys.profile(workspaceId, userId),
    queryFn: () =>
      call(
        api.GET("/workspaces/{workspace_id}/people/{user_id}/profile", {
          params: { path: { workspace_id: workspaceId, user_id: userId } },
        }),
      ),
  });
}

export function useCvImports(workspaceId: string, enabled: boolean) {
  return useQuery({
    queryKey: peopleKeys.imports(workspaceId),
    queryFn: () =>
      call(
        api.GET("/workspaces/{workspace_id}/cv-imports", {
          params: { path: { workspace_id: workspaceId } },
        }),
      ),
    enabled,
    // While the agent works, check every 2 s; stop once nothing is queued.
    refetchInterval: (query) =>
      query.state.data?.some((cvImport) => cvImport.status === "queued") ? 2000 : false,
  });
}
