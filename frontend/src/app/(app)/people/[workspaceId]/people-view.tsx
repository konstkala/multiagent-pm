"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { Avatar } from "@/components/tickets";
import { Alert, Badge, Loading } from "@/components/ui";
import { ApiError, errorText } from "@/lib/api/client";
import { useMe, usePeople } from "@/lib/queries";

export function PeopleView() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const people = usePeople(workspaceId);
  const me = useMe();

  if (people.isPending) return <Loading />;
  if (people.isError) {
    const forbidden = people.error instanceof ApiError && people.error.status === 403;
    return (
      <div className="flex flex-col gap-3">
        <Alert tone={forbidden ? "info" : "error"}>
          {forbidden ? "Only managers can see everyone's profiles." : errorText(people.error)}
        </Alert>
        {forbidden && me.data ? (
          <Link href={`/people/${workspaceId}/${me.data.id}`} className="text-sm text-link hover:underline">
            See your own profile
          </Link>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Link href="/projects" className="text-sm text-link hover:underline">
        ← Projects
      </Link>
      <h1 className="text-2xl font-semibold tracking-tight">People</h1>
      <ul className="divide-y divide-border rounded-sm border border-border bg-surface">
        {people.data.map((person) => (
          <li key={person.user_id}>
            <Link
              href={`/people/${workspaceId}/${person.user_id}`}
              className="flex items-center gap-3 px-4 py-3 hover:bg-subtle"
            >
              <Avatar name={person.display_name} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{person.display_name}</p>
                <p className="truncate text-xs text-muted">{person.headline || "No profile yet"}</p>
              </div>
              <span className="text-xs text-muted">{person.skill_count} skills</span>
              <Badge>{person.workspace_role}</Badge>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
