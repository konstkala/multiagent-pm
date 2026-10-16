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
