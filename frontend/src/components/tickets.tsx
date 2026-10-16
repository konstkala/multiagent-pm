import type { Member } from "@/lib/api/client";
import {
  PRIORITY_STYLE,
  STATUS_LABEL,
  STATUS_STYLE,
  formatDay,
  isOverdue,
  type Priority,
  type Status,
} from "@/lib/tickets";

export function StatusPill({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

export function PriorityText({ priority }: { priority: Priority | null }) {
  if (!priority) return <span className="text-xs text-muted">–</span>;
  return <span className={`text-xs font-medium capitalize ${PRIORITY_STYLE[priority]}`}>{priority}</span>;
}

export function Avatar({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <span
      title={name}
      className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-accent/10 text-[10px] font-semibold text-accent"
    >
      {initials || "?"}
    </span>
  );
}

export function AssigneeName({ assigneeId, members }: { assigneeId: string | null; members: Member[] }) {
  if (!assigneeId) return <span className="text-xs text-muted">Unassigned</span>;
  const member = members.find((m) => m.user_id === assigneeId);
  const name = member?.display_name ?? "Former member";
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      <Avatar name={name} />
      <span className="truncate text-xs">{name}</span>
    </span>
  );
}

export function DueDate({ dueDate, status }: { dueDate: string | null; status: Status }) {
  if (!dueDate) return <span className="text-xs text-muted">–</span>;
  const overdue = isOverdue(dueDate, status);
  return (
    <span className={`text-xs ${overdue ? "font-semibold text-danger" : "text-muted"}`}>
      {overdue ? "Overdue · " : ""}
      {formatDay(dueDate)}
    </span>
  );
}

export function Points({ points }: { points: number | null }) {
  if (points === null) return null;
  return (
    <span
      title={`${points} story points`}
      className="inline-flex min-w-5 justify-center rounded bg-background px-1 text-xs font-medium text-muted"
    >
      {points}
    </span>
  );
}
