"use client";

import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { RangePicker, useDateRange } from "@/components/range-picker";
import { Alert, Card, Loading } from "@/components/ui";
import { errorText, type Schemas } from "@/lib/api/client";
import { useProject, useProjectDashboard } from "@/lib/queries";
import { STATUS_LABEL, formatDay } from "@/lib/tickets";

type Dashboard = Schemas["ProjectDashboard"];

export function DashboardView() {
  const { projectId } = useParams<{ projectId: string }>();
  const [range, setRange] = useDateRange();
  const project = useProject(projectId);
  const dashboard = useProjectDashboard(projectId, range);

  return (
    <div className="flex flex-col gap-6">
      <RangePicker value={range} onChange={setRange} />
      {dashboard.isPending ? <Loading /> : null}
      {dashboard.isError ? <Alert tone="error">{errorText(dashboard.error)}</Alert> : null}
      {dashboard.data ? (
        <TeamKpis data={dashboard.data} isManager={project.data?.role === "manager"} />
      ) : null}
    </div>
  );
}

function TeamKpis({ data, isManager }: { data: Dashboard; isManager: boolean }) {
  return (
    <>
      {data.start < data.exact_history_since ? (
        <Alert tone="info">
          History before {formatDay(data.exact_history_since)} was rebuilt from each ticket&apos;s
          state at the time, so older times are approximate.
        </Alert>
      ) : null}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Created">{data.created}</Stat>
        <Stat label="Done">{data.done}</Stat>
        <Stat label="Cycle time" hint="First In progress to Done; median, p90 in brackets">
          <DurationText value={data.cycle_time} />
        </Stat>
        <Stat label="Lead time" hint="Created to Done; median, p90 in brackets">
          <DurationText value={data.lead_time} />
        </Stat>
        <Stat label="Overdue now">{data.overdue}</Stat>
      </div>

      <Card title="Created and done per week">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.weeks.map((w) => ({ ...w, label: formatDay(w.week) }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={32} />
              <Tooltip />
              <Legend />
              <Bar dataKey="created" name="Created" fill="var(--muted)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="done" name="Done" fill="var(--accent)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Open now">
          <dl className="grid grid-cols-[1fr_auto] gap-y-1.5 text-sm">
            {data.open_by_status.map((s) => (
              <Row key={s.status} label={STATUS_LABEL[s.status]} value={s.count} />
            ))}
            <dt className="col-span-2 mt-2 text-xs font-medium text-muted">By age</dt>
            <Row label="Up to 7 days" value={data.open_age.up_to_7_days} />
            <Row label="8 to 30 days" value={data.open_age.days_8_to_30} />
            <Row label="Over 30 days" value={data.open_age.over_30_days} />
          </dl>
        </Card>
        <Card title={isManager ? "Workload" : "Your workload"}>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="pb-2 font-medium">Person</th>
                <th className="pb-2 text-right font-medium">Open</th>
                <th className="pb-2 text-right font-medium" title="Unpointed tickets count as 3">
                  Points
                </th>
                <th className="pb-2 text-right font-medium">Overdue</th>
              </tr>
            </thead>
            <tbody>
              {data.workload.map((row) => (
                <tr key={row.user_id} className="border-t border-border">
                  <td className="py-1.5">{row.display_name}</td>
                  <td className="py-1.5 text-right">{row.open_tickets}</td>
                  <td className="py-1.5 text-right">{row.open_points}</td>
                  <td className={`py-1.5 text-right ${row.overdue ? "text-danger" : ""}`}>{row.overdue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}

function Stat({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4" title={hint}>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <>
      <dt>{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </>
  );
}

function DurationText({ value }: { value: Dashboard["cycle_time"] }) {
  if (value.median_days === null) return <span className="text-muted">–</span>;
  return (
    <>
      {value.median_days} d <span className="text-sm font-normal text-muted">({value.p90_days} d)</span>
    </>
  );
}
