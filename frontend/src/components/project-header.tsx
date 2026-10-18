"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

import { Alert, Badge, Loading } from "@/components/ui";
import { errorText } from "@/lib/api/client";
import { useProject } from "@/lib/queries";

export function ProjectHeader() {
  const { projectId } = useParams<{ projectId: string }>();
  const pathname = usePathname();
  const project = useProject(projectId);
  const base = `/projects/${projectId}`;
  const tabs = [
    { href: base, label: "Tickets", active: pathname === base || pathname.startsWith(`${base}/tickets`) },
    { href: `${base}/board`, label: "Board", active: pathname === `${base}/board` },
    { href: `${base}/dashboard`, label: "Dashboard", active: pathname === `${base}/dashboard` },
    { href: `${base}/team`, label: "Team", active: pathname === `${base}/team` },
  ];

  if (project.isPending) return <Loading />;
  if (project.isError) return <Alert tone="error">{errorText(project.error)}</Alert>;
  return (
    <div className="flex flex-col gap-4 border-b border-border pb-0">
      <div className="flex flex-col gap-1">
        <Link href="/projects" className="text-sm text-link hover:underline">
          ← All projects
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{project.data.name}</h1>
          <span className="font-mono text-sm text-muted">{project.data.key}</span>
          <Badge>{project.data.role}</Badge>
        </div>
      </div>
      <nav aria-label="Project sections" className="-mb-px flex gap-1">
        {tabs.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={tab.active ? "page" : undefined}
            className={`border-b-2 px-3 py-2 text-sm font-medium ${
              tab.active
                ? "border-accent text-foreground"
                : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {tab.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
