"use client";

import Link from "next/link";
import { useState } from "react";

import { Alert, Button, Loading } from "@/components/ui";
import { errorText, type Schemas } from "@/lib/api/client";
import { useCalendar } from "@/lib/queries";
import { STATUS_STYLE, isOverdue } from "@/lib/tickets";

type DueTicket = Schemas["CalendarTicket"];

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const monthFormat = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" });

/** A month grid of due dates: six weeks from the Monday before the 1st (42 days). */
export function CalendarView() {
  const [month, setMonth] = useState(() => firstOfMonth(new Date()));
  const [mine, setMine] = useState(false);
  const [project, setProject] = useState("");
  const days = gridDays(month);
  const calendar = useCalendar({ start: isoDay(days[0]), end: isoDay(days[days.length - 1]) }, mine);
  const tickets = (calendar.data ?? []).filter((t) => !project || t.project_id === project);
  const projects = projectOptions(calendar.data ?? []);
  const byDay = Map.groupBy(tickets, (t) => t.due_date);
  const today = isoDay(new Date());

  const shift = (months: number) => setMonth(new Date(month.getFullYear(), month.getMonth() + months, 1));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{monthFormat.format(month)}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Button variant="secondary" onClick={() => shift(-1)} aria-label="Previous month">
            ←
          </Button>
          <Button variant="secondary" onClick={() => setMonth(firstOfMonth(new Date()))}>
            Today
          </Button>
          <Button variant="secondary" onClick={() => shift(1)} aria-label="Next month">
            →
          </Button>
          <select
            aria-label="Project"
            value={project}
            onChange={(event) => setProject(event.target.value)}
            className="rounded-md border border-border bg-surface px-2 py-1.5"
          >
            <option value="">All projects</option>
            {projects.map(([id, key]) => (
              <option key={id} value={id}>
                {key}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={mine} onChange={(event) => setMine(event.target.checked)} />
            Only mine
          </label>
        </div>
      </div>
      {calendar.isPending ? <Loading /> : null}
      {calendar.isError ? <Alert tone="error">{errorText(calendar.error)}</Alert> : null}
      <div className="grid grid-cols-7 overflow-hidden rounded-lg border border-border bg-border text-sm" style={{ gap: 1 }}>
        {WEEKDAYS.map((day) => (
          <div key={day} className="bg-background px-2 py-1 text-xs font-medium text-muted">
            {day}
          </div>
        ))}
        {days.map((day) => {
          const iso = isoDay(day);
          const inMonth = day.getMonth() === month.getMonth();
          return (
            <div key={iso} className={`min-h-24 bg-surface p-1.5 ${inMonth ? "" : "opacity-50"}`}>
              <div className={`mb-1 text-xs ${iso === today ? "font-semibold text-accent" : "text-muted"}`}>
                {day.getDate()}
              </div>
              <ul className="flex flex-col gap-1">
                {(byDay.get(iso) ?? []).map((ticket) => (
                  <DueItem key={ticket.id} ticket={ticket} />
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DueItem({ ticket }: { ticket: DueTicket }) {
  const late = isOverdue(ticket.due_date, ticket.status);
  return (
    <li>
      <Link
        href={`/projects/${ticket.project_id}/tickets/${ticket.id}`}
        title={ticket.title}
        className={`block truncate rounded border px-1.5 py-0.5 text-xs hover:underline ${
          late ? "border-red-200 bg-red-50 text-danger" : STATUS_STYLE[ticket.status]
        }`}
      >
        <span className="font-mono">{ticket.key}</span> {ticket.title}
      </Link>
    </li>
  );
}

function firstOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function gridDays(month: Date): Date[] {
  const offset = (month.getDay() + 6) % 7; // days since Monday
  return Array.from(
    { length: 42 },
    (_, i) => new Date(month.getFullYear(), month.getMonth(), 1 - offset + i),
  );
}

function projectOptions(tickets: DueTicket[]): [string, string][] {
  const keys = new Map(tickets.map((t) => [t.project_id, t.key.split("-")[0]]));
  return [...keys.entries()].sort((a, b) => a[1].localeCompare(b[1]));
}

function isoDay(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}
