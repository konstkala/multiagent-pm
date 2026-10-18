"use client";

import Link from "next/link";
import { useState } from "react";

import { Alert, Button, Loading } from "@/components/ui";
import { errorText, type Schemas } from "@/lib/api/client";
import { useCalendar } from "@/lib/queries";
import { LOCALE, STATUS_STYLE, isOverdue } from "@/lib/tickets";

type DueTicket = Schemas["CalendarTicket"];

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const monthFormat = new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric" });
const agendaDay = new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long" });

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
            className="rounded-sm border border-border bg-surface px-2 py-1.5"
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
      <Agenda days={days} month={month} byDay={byDay} />
      <div className="hidden grid-cols-7 overflow-hidden md:grid rounded-sm border border-border bg-border text-sm" style={{ gap: 1 }}>
        {WEEKDAYS.map((day) => (
          <div key={day} className="bg-subtle px-2 py-1 text-xs font-medium text-muted">
            {day}
          </div>
        ))}
        {days.map((day) => {
          const iso = isoDay(day);
          const inMonth = day.getMonth() === month.getMonth();
          return (
            <div key={iso} className={`min-h-24 bg-surface p-1.5 ${inMonth ? "" : "bg-subtle"}`}>
              <div className={`mb-1 text-xs ${iso === today ? "font-semibold text-link" : "text-muted"}`}>
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

/** Phones: a month grid is too small to read, so list the days that have something due. */
function Agenda({
  days,
  month,
  byDay,
}: {
  days: Date[];
  month: Date;
  byDay: Map<string, DueTicket[]>;
}) {
  const due = days.filter((day) => day.getMonth() === month.getMonth() && byDay.has(isoDay(day)));
  if (!due.length) return <p className="text-sm text-muted md:hidden">Nothing due this month.</p>;
  return (
    <ol className="flex flex-col gap-4 md:hidden">
      {due.map((day) => (
        <li key={isoDay(day)} className="flex flex-col gap-1.5">
          <h2 className="text-xs font-semibold text-muted">{agendaDay.format(day)}</h2>
          <ul className="flex flex-col gap-1">
            {(byDay.get(isoDay(day)) ?? []).map((ticket) => (
              <DueItem key={ticket.id} ticket={ticket} />
            ))}
          </ul>
        </li>
      ))}
    </ol>
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
          late ? "border-danger/40 bg-danger/10 text-danger" : STATUS_STYLE[ticket.status]
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
