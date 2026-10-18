import type { Schemas } from "@/lib/api/client";

export type Status = Schemas["TicketStatus"];
export type Category = Schemas["TicketCategory"];
export type Priority = Schemas["TicketPriority"];

export const STATUSES: readonly Status[] = ["todo", "in_progress", "in_review", "done", "cancelled"];
export const OPEN_STATUSES: readonly Status[] = ["todo", "in_progress", "in_review"];
export const CATEGORIES: readonly Category[] = [
  "bug",
  "implementation",
  "improvement",
  "analysis",
  "task",
];
export const PRIORITIES: readonly Priority[] = ["urgent", "high", "medium", "low"];
export const STORY_POINTS = [1, 2, 3, 5, 8, 13] as const;

export const STATUS_LABEL: Record<Status, string> = {
  todo: "To do",
  in_progress: "In progress",
  in_review: "In review",
  done: "Done",
  cancelled: "Cancelled",
};

// Semantic colours: they say where work stands, separate from the accent colour.
export const STATUS_STYLE: Record<Status, string> = {
  todo: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700",
  in_progress: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-900",
  in_review: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-900",
  done: "bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-900",
  cancelled: "bg-zinc-100 text-zinc-500 border-zinc-200 line-through dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-800",
};

export const PRIORITY_STYLE: Record<Priority, string> = {
  urgent: "text-red-700 dark:text-red-400",
  high: "text-orange-700 dark:text-orange-400",
  medium: "text-slate-700 dark:text-slate-300",
  low: "text-slate-500 dark:text-slate-400",
};

/** A form value narrowed to one of the allowed options, or null. */
export function pick<T extends string>(options: readonly T[], value: string): T | null {
  return options.find((option) => option === value) ?? null;
}

export function ticketKey(projectKey: string, number: number): string {
  return `${projectKey}-${number}`;
}

export function isClosed(status: Status): boolean {
  return status === "done" || status === "cancelled";
}

/** Due dates are calendar days ("2026-11-30"), compared without time zones. */
export function isOverdue(dueDate: string | null, status: Status): boolean {
  if (!dueDate || isClosed(status)) return false;
  return dueDate < new Date().toISOString().slice(0, 10);
}

// The interface is English, so dates are too (day first), whatever the browser's language.
export const LOCALE = "en-GB";
const dayFormat = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short" });
const timeFormat = new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeStyle: "short" });

export function formatDay(isoDate: string): string {
  return dayFormat.format(new Date(`${isoDate}T00:00:00`));
}

export function formatTime(isoDateTime: string): string {
  return timeFormat.format(new Date(isoDateTime));
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}
