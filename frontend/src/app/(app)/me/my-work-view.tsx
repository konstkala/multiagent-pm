"use client";

import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { RangePicker, useDateRange } from "@/components/range-picker";
import { StatusPill } from "@/components/tickets";
import { Alert, Card, Loading } from "@/components/ui";
import { errorText, type Schemas } from "@/lib/api/client";
import { useMyDashboard } from "@/lib/queries";
import { STATUS_LABEL, formatDay } from "@/lib/tickets";

type MyTicket = Schemas["MyTicket"];

export function MyWorkView() {
  const [range, setRange] = useDateRange();
  const mine = useMyDashboard(range);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">My work</h1>
      <RangePicker value={range} onChange={setRange} />
      {mine.isPending ? <Loading /> : null}
      {mine.isError ? <Alert tone="error">{errorText(mine.error)}</Alert> : null}
      {mine.data ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {mine.data.open_by_status.map((s) => (
              <Stat key={s.status} label={STATUS_LABEL[s.status]} value={s.count} />
            ))}
            <Stat label="Open points" value={mine.data.open_points} />
            <Stat label="Done in range" value={mine.data.done} />
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <TicketList title="Overdue" tickets={mine.data.overdue} empty="Nothing overdue." />
            <TicketList title="Due in the next 7 days" tickets={mine.data.due_soon} empty="Nothing due soon." />
          </div>
          <Card title="Done per week">
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mine.data.weeks.map((w) => ({ ...w, label: formatDay(w.week) }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={32} />
                  <Tooltip />
                  <Bar dataKey="done" name="Done" fill="var(--accent)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-sm border border-border bg-surface p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </div>
  );
}

function TicketList({ title, tickets, empty }: { title: string; tickets: MyTicket[]; empty: string }) {
  return (
    <Card title={`${title} (${tickets.length})`}>
      {tickets.length ? (
        <ul className="flex flex-col gap-2.5">
          {tickets.map((ticket) => (
            <li key={ticket.id} className="flex items-center justify-between gap-3">
              <Link
                href={`/projects/${ticket.project_id}/tickets/${ticket.id}`}
                className="min-w-0 truncate text-sm hover:text-link hover:underline"
              >
                <span className="font-mono text-xs text-muted">{ticket.key}</span> {ticket.title}
              </Link>
              <span className="flex shrink-0 items-center gap-2">
                {ticket.due_date ? <span className="text-xs text-muted">{formatDay(ticket.due_date)}</span> : null}
                <StatusPill status={ticket.status} />
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">{empty}</p>
      )}
    </Card>
  );
}
