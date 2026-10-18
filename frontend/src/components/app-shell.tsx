"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useState, useSyncExternalStore, type ReactNode } from "react";

import { Alert, Button, Loading } from "@/components/ui";
import { api, errorText, send, type Workspace } from "@/lib/api/client";
import { useMe, useProjects, useWorkspaces } from "@/lib/queries";

const THEMES = ["system", "light", "dark"] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const pathname = usePathname();
  // Open "for this path": tapping a link on a phone navigates, which closes the menu.
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === pathname;

  return (
    <div className="flex min-h-screen flex-1 flex-col md:flex-row">
      <header className="flex items-center justify-between border-b border-border px-4 py-3 md:hidden">
        <Link href="/projects" className="font-semibold tracking-tight">
          Multiagent PM
        </Link>
        <button
          type="button"
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpenAt(open ? null : pathname)}
          className="rounded-sm border border-control px-3 py-1.5 text-sm"
        >
          Menu
        </button>
      </header>

      <aside
        id="sidebar"
        className={`${open ? "flex" : "hidden"} w-full shrink-0 flex-col gap-6 border-border px-3 py-5 md:sticky md:top-0 md:flex md:h-screen md:w-60 md:overflow-y-auto md:border-r`}
      >
        <Link href="/projects" className="hidden px-2 font-semibold tracking-tight md:block">
          Multiagent PM
        </Link>
        <nav aria-label="Main" className="flex flex-col gap-0.5">
          <NavLink href="/me" current={pathname === "/me"}>
            My work
          </NavLink>
          <NavLink href="/calendar" current={pathname === "/calendar"}>
            Calendar
          </NavLink>
        </nav>
        <ProjectList pathname={pathname} />
        {me.data ? <Account name={me.data.display_name} /> : null}
      </aside>

      <main className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 py-8 md:px-8">
        {me.isPending ? <Loading /> : null}
        {me.isError ? <Alert tone="error">{errorText(me.error)}</Alert> : null}
        {me.data ? children : null}
      </main>
    </div>
  );
}

function NavLink({ href, current, children }: { href: string; current: boolean; children: ReactNode }) {
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={`rounded-sm px-2 py-1.5 text-sm hover:bg-subtle ${
        current ? "bg-subtle font-semibold shadow-[inset_2px_0_0_var(--accent)]" : ""
      }`}
    >
      {children}
    </Link>
  );
}

function ProjectList({ pathname }: { pathname: string }) {
  const workspaces = useWorkspaces();
  return (
    <nav aria-label="Projects" className="flex flex-col gap-4">
      <NavLink href="/projects" current={pathname === "/projects"}>
        All projects
      </NavLink>
      {workspaces.data?.map((workspace) => (
        <WorkspaceProjects key={workspace.id} workspace={workspace} pathname={pathname} />
      ))}
    </nav>
  );
}

function WorkspaceProjects({ workspace, pathname }: { workspace: Workspace; pathname: string }) {
  const projects = useProjects(workspace.id);
  return (
    <div className="flex flex-col gap-0.5">
      <span className="px-2 pb-1 text-xs text-muted">{workspace.name}</span>
      {projects.data?.map((project) => (
        <NavLink
          key={project.id}
          href={`/projects/${project.id}`}
          current={pathname.startsWith(`/projects/${project.id}`)}
        >
          {project.name}
        </NavLink>
      ))}
      <NavLink href={`/people/${workspace.id}`} current={pathname.startsWith(`/people/${workspace.id}`)}>
        People
      </NavLink>
    </div>
  );
}

function Account({ name }: { name: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [signingOut, setSigningOut] = useState(false);

  async function signOut() {
    setSigningOut(true);
    await send(api.POST("/auth/sign-out")).catch(() => undefined);
    queryClient.clear(); // drop every cached answer from this account
    router.replace("/sign-in");
  }

  return (
    <div className="mt-auto flex flex-col gap-3 border-t border-border px-2 pt-4">
      <span className="truncate text-sm font-medium">{name}</span>
      <ThemeToggle />
      <Button variant="secondary" onClick={signOut} pending={signingOut}>
        Sign out
      </Button>
    </div>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  // The stored theme is unknown on the server: false there, true once in the browser.
  const mounted = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );

  return (
    <div role="group" aria-label="Theme" className="flex overflow-hidden rounded-sm border border-control text-xs">
      {THEMES.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={mounted && theme === option}
          onClick={() => setTheme(option)}
          className={`flex-1 px-2 py-1.5 capitalize ${
            mounted && theme === option ? "bg-accent text-on-accent" : "hover:bg-subtle"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
