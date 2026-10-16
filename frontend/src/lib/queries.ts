"use client";

import { useQuery } from "@tanstack/react-query";

import { api, call } from "@/lib/api/client";

/** Query keys in one place, so mutations invalidate exactly what they change. */
export const keys = {
  me: ["me"] as const,
  workspaces: ["workspaces"] as const,
  projects: (workspaceId: string) => ["workspaces", workspaceId, "projects"] as const,
  project: (projectId: string) => ["projects", projectId] as const,
  members: (projectId: string) => ["projects", projectId, "members"] as const,
  tickets: (projectId: string) => ["projects", projectId, "tickets"] as const,
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

export function useTickets(projectId: string) {
  return useQuery({
    queryKey: keys.tickets(projectId),
    queryFn: () =>
      call(
        api.GET("/projects/{project_id}/tickets", {
          params: { path: { project_id: projectId }, query: { limit: 50 } },
        }),
      ),
  });
}
