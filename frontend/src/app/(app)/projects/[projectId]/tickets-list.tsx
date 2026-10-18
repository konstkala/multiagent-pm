"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { CreateTicketForm } from "@/components/create-ticket";
import { AssigneeName, DueDate, Points, PriorityText, StatusPill } from "@/components/tickets";
import { Alert, Button, Card, Loading } from "@/components/ui";
import { errorText } from "@/lib/api/client";
import { useMembers, useProject, useTickets, type TicketFilters } from "@/lib/queries";
import { CATEGORIES, STATUSES, STATUS_LABEL, pick, ticketKey, type Status } from "@/lib/tickets";

const PAGE_SIZE = 50;

/** Filters live in the URL, so a filtered view can be bookmarked or shared. */
function filtersFrom(params: URLSearchParams): TicketFilters {
  const status = (params.get("status") ?? "")
    .split(",")
    .map((s) => pick(STATUSES, s))
    .filter((s): s is Status => s !== null);
  const assignee = params.get("assignee");
  return {
    status: status.length ? status : undefined,
    assignee_id: assignee && assignee !== "none" ? assignee : undefined,
    unassigned: assignee === "none" || undefined,
    category: pick(CATEGORIES, params.get("category") ?? "") ?? undefined,
    label: params.get("label") || undefined,
    q: params.get("q") || undefined,
    limit: PAGE_SIZE,
    offset: Math.max(0, Number(params.get("page") ?? "0")) * PAGE_SIZE,
  };
}

export function TicketsList() {
  const { projectId } = useParams<{ projectId: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const filters = filtersFrom(params);
  const project = useProject(projectId);
  const members = useMembers(projectId);
  const tickets = useTickets(projectId, filters);
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState(params.get("q") ?? "");

  function setParam(name: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    if (name !== "page") next.delete("page"); // a new filter starts from page one
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }

  // Search as you type, but only after a short pause.
  useEffect(() => {
    if (search === (params.get("q") ?? "")) return;
    const timer = setTimeout(() => {
      const next = new URLSearchParams(params);
      if (search) next.set("q", search);
      else next.delete("q");
      next.delete("page");
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    }, 300);
    return () => clearTimeout(timer);
  }, [search, params, pathname, router]);

  if (project.isPending || members.isPending) return <Loading />;
  if (project.isError) return <Alert tone="error">{errorText(project.error)}</Alert>;
  const memberList = members.data ?? [];
  const isManager = project.data.role === "manager";
  const activeStatuses = new Set(filters.status ?? []);
  const page = Math.floor((filters.offset ?? 0) / PAGE_SIZE);

  function toggleStatus(status: Status) {
    const next = new Set(activeStatuses);
    if (next.has(status)) next.delete(status);
    else next.add(status);
    setParam("status", [...next].join(",") || null);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-56 flex-1 flex-col gap-1.5">
          <label htmlFor="ticket-search" className="text-sm font-medium">
            Search
          </label>
          <input
            id="ticket-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Title, description or number"
            className="rounded-sm border border-control bg-surface px-3 py-2 text-sm outline-none focus:border-ring"
          />
        </div>
        <FilterSelect
          id="filter-assignee"
          label="Assignee"
          value={params.get("assignee") ?? ""}
          onChange={(v) => setParam("assignee", v)}
          options={[
            { value: "none", label: "Unassigned" },
            ...memberList.map((m) => ({ value: m.user_id, label: m.display_name })),
          ]}
        />
        <FilterSelect
          id="filter-category"
          label="Category"
          value={filters.category ?? ""}
          onChange={(v) => setParam("category", v)}
          options={CATEGORIES.map((c) => ({ value: c, label: c }))}
        />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="filter-label" className="text-sm font-medium">
            Label
          </label>
          <input
            id="filter-label"
            defaultValue={filters.label ?? ""}
            onBlur={(event) => setParam("label", event.target.value.trim().toLowerCase() || null)}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
            }}
            placeholder="backend"
            className="w-32 rounded-sm border border-control bg-surface px-3 py-2 text-sm outline-none focus:border-ring"
          />
        </div>
        {isManager && !creating ? <Button onClick={() => setCreating(true)}>New ticket</Button> : null}
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        {STATUSES.map((status) => (
          <button
            key={status}
            type="button"
            aria-pressed={activeStatuses.has(status)}
            onClick={() => toggleStatus(status)}
            className={`rounded-sm border px-3 py-1 text-xs font-medium ${
              activeStatuses.has(status)
                ? "border-accent bg-accent text-on-accent"
                : "border-border bg-surface text-muted hover:text-foreground"
            }`}
          >
            {STATUS_LABEL[status]}
          </button>
        ))}
      </div>

      {creating ? (
        <Card title="New ticket">
          <CreateTicketForm
            projectId={projectId}
            members={memberList}
            onCreated={(ticket) => router.push(`/projects/${projectId}/tickets/${ticket.id}`)}
            onCancel={() => setCreating(false)}
          />
        </Card>
      ) : null}

      <div className="overflow-x-auto rounded-sm border border-border bg-surface">
        {tickets.isPending ? (
          <div className="p-4">
            <Loading />
          </div>
        ) : null}
        {tickets.isError ? (
          <div className="p-4">
            <Alert tone="error">{errorText(tickets.error)}</Alert>
          </div>
        ) : null}
        {tickets.data?.items.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted">
            {params.toString() ? "No tickets match these filters." : "No tickets yet."}
          </p>
        ) : null}
        {tickets.data && tickets.data.items.length > 0 ? (
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Key</th>
                <th className="px-4 py-2 font-medium">Title</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Priority</th>
                <th className="px-4 py-2 font-medium">Assignee</th>
                <th className="px-4 py-2 font-medium">Pts</th>
                <th className="px-4 py-2 font-medium">Due</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {tickets.data.items.map((ticket) => (
                <tr key={ticket.id} className="hover:bg-subtle">
                  <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-muted">
                    {ticketKey(project.data.key, ticket.number)}
                  </td>
                  <td className="max-w-md px-4 py-2.5">
                    <Link
                      href={`/projects/${projectId}/tickets/${ticket.id}`}
                      className="line-clamp-1 font-medium hover:text-link hover:underline"
                    >
                      {ticket.title}
                    </Link>
                    {ticket.labels.length ? (
                      <span className="mt-0.5 block truncate text-xs text-muted">
                        {ticket.labels.join(" · ")}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusPill status={ticket.status} />
                  </td>
                  <td className="px-4 py-2.5">
                    <PriorityText priority={ticket.priority} />
                  </td>
                  <td className="max-w-40 px-4 py-2.5">
                    <AssigneeName assigneeId={ticket.assignee_id} members={memberList} />
                  </td>
                  <td className="px-4 py-2.5">
                    <Points points={ticket.story_points} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <DueDate dueDate={ticket.due_date} status={ticket.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      {tickets.data && tickets.data.total > PAGE_SIZE ? (
        <div className="flex items-center justify-between text-sm text-muted">
          <span>
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, tickets.data.total)} of{" "}
            {tickets.data.total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={page === 0}
              onClick={() => setParam("page", String(page - 1))}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              disabled={(page + 1) * PAGE_SIZE >= tickets.data.total}
              onClick={() => setParam("page", String(page + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function FilterSelect({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string | null) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value || null)}
        className="rounded-sm border border-control bg-surface px-3 py-2 text-sm outline-none focus:border-ring"
      >
        <option value="">Any</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
