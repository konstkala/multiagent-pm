"use client";

import { Bar, BarChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { DateRange } from "@/components/range-picker";
import { Alert, Card, Loading } from "@/components/ui";
import { errorText, type Schemas } from "@/lib/api/client";
import { useAgentMetrics } from "@/lib/queries";

type Cost = Schemas["AgentCost"];

const FIELD_LABEL: Record<string, string> = {
  category: "Category",
  labels: "Labels",
  priority: "Priority",
  story_points: "Story points",
};

/** Managers only. Quality (what managers kept), hit rate, cost and speed per agent. */
export function AgentMetrics({ projectId, range }: { projectId: string; range: DateRange }) {
  const metrics = useAgentMetrics(projectId, range);

  if (metrics.isPending) return <Loading />;
  if (metrics.isError) return <Alert tone="error">{errorText(metrics.error)}</Alert>;
  const { triage, assignment } = metrics.data;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">AI agents</h2>
      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Triage">
          <div className="flex flex-col gap-4 text-sm">
            <p>
              {triage.runs} runs: {triage.accepted} accepted, {triage.dismissed} dismissed,{" "}
              {triage.failed} failed, {triage.waiting} waiting.
            </p>
            {triage.accepted ? (
              <div className="h-44" aria-label="What managers did with each suggested field">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    layout="vertical"
                    data={triage.fields.map((f) => ({ ...f, label: FIELD_LABEL[f.field] ?? f.field }))}
                  >
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
                    <YAxis type="category" dataKey="label" width={90} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="kept" name="Kept" stackId="a" fill="var(--success)" />
                    <Bar dataKey="edited" name="Edited" stackId="a" fill="var(--accent)" />
                    <Bar dataKey="left_out" name="Left out" stackId="a" fill="var(--border)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs text-muted">No accepted suggestions in this range yet.</p>
            )}
            <p className="text-xs text-muted">
              Set by the agent itself: {triage.auto_applied} fields, {triage.auto_applied_unchanged} still
              unchanged.
            </p>
            <CostLine cost={triage.cost} />
          </div>
        </Card>
        <Card title="Assignment">
          <div className="flex flex-col gap-4 text-sm">
            <p>
              {assignment.runs} suggestions, {assignment.decided} followed by an assignment.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <Rate label="Picked the first" value={assignment.top1_rate} />
              <Rate label="Picked one of the 3" value={assignment.top3_rate} />
            </div>
            <p className="text-xs text-muted">
              Ranking p95: {assignment.score_p95_ms === null ? "–" : `${Math.round(assignment.score_p95_ms)} ms`}
            </p>
            <CostLine cost={assignment.cost} />
          </div>
        </Card>
      </div>
    </section>
  );
}

function Rate({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-sm border border-border p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-xl font-semibold">{value === null ? "–" : `${Math.round(value * 100)}%`}</div>
    </div>
  );
}

function CostLine({ cost }: { cost: Cost }) {
  if (!cost.runs) return <p className="border-t border-border pt-3 text-xs text-muted">No AI calls yet.</p>;
  const seconds = (ms: number | null) => (ms === null ? "–" : `${(ms / 1000).toFixed(1)} s`);
  return (
    <p className="border-t border-border pt-3 text-xs text-muted">
      ${cost.cost_usd.toFixed(4)} total · ${cost.cost_per_run_usd?.toFixed(5)} per run · latency p50{" "}
      {seconds(cost.latency_p50_ms)}, p95 {seconds(cost.latency_p95_ms)}
    </p>
  );
}
