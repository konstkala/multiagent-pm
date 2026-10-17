"use client";

import { useState } from "react";

/** Inclusive calendar days, as the API takes them ("2026-10-17"). */
export type DateRange = { start: string; end: string };

const PRESETS = [7, 30, 90] as const;

export function lastDays(days: number): DateRange {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - (days - 1));
  return { start: isoDay(start), end: isoDay(end) };
}

export function useDateRange(days = 30) {
  return useState<DateRange>(() => lastDays(days));
}

export function RangePicker({ value, onChange }: { value: DateRange; onChange: (range: DateRange) => void }) {
  const preset = PRESETS.find((days) => {
    const range = lastDays(days);
    return range.start === value.start && range.end === value.end;
  });

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {PRESETS.map((days) => (
        <button
          key={days}
          type="button"
          aria-pressed={preset === days}
          onClick={() => onChange(lastDays(days))}
          className={`rounded-md border px-2.5 py-1 ${
            preset === days ? "border-accent bg-accent text-white" : "border-border bg-surface hover:bg-background"
          }`}
        >
          {days} days
        </button>
      ))}
      <label className="flex items-center gap-1 text-muted">
        From
        <input
          type="date"
          value={value.start}
          max={value.end}
          onChange={(event) => event.target.value && onChange({ ...value, start: event.target.value })}
          className="rounded-md border border-border bg-surface px-2 py-1 text-foreground"
        />
      </label>
      <label className="flex items-center gap-1 text-muted">
        to
        <input
          type="date"
          value={value.end}
          min={value.start}
          onChange={(event) => event.target.value && onChange({ ...value, end: event.target.value })}
          className="rounded-md border border-border bg-surface px-2 py-1 text-foreground"
        />
      </label>
    </div>
  );
}

/** The local calendar day, not UTC: "today" is the user's today. */
function isoDay(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}
