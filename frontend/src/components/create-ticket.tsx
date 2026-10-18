"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, type FormEvent } from "react";

import { Alert, Button, Select, TextField } from "@/components/ui";
import { api, call, errorText, type Member, type Schemas, type Ticket } from "@/lib/api/client";
import { keys } from "@/lib/queries";
import { CATEGORIES, PRIORITIES, STORY_POINTS, pick } from "@/lib/tickets";

type Props = {
  projectId: string;
  members: Member[];
  parentId?: string;
  onCreated?: (ticket: Ticket) => void;
  onCancel?: () => void;
};

export function CreateTicketForm({ projectId, members, parentId, onCreated, onCancel }: Props) {
  const formRef = useRef<HTMLFormElement>(null);
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: (body: Schemas["TicketCreate"]) =>
      call(
        api.POST("/projects/{project_id}/tickets", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: async (ticket) => {
      formRef.current?.reset();
      await queryClient.invalidateQueries({ queryKey: keys.ticketLists(projectId) });
      onCreated?.(ticket);
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    create.mutate({
      title: text("title"),
      description: text("description"),
      category: pick(CATEGORIES, text("category")),
      priority: pick(PRIORITIES, text("priority")),
      story_points: toPoints(text("story_points")),
      due_date: text("due_date") || null,
      assignee_id: text("assignee_id") || null,
      labels: splitLabels(text("labels")),
      parent_id: parentId ?? null,
    });
  }

  return (
    <form ref={formRef} onSubmit={onSubmit} className="flex flex-col gap-4">
      {create.isError ? <Alert tone="error">{errorText(create.error)}</Alert> : null}
      <TextField label="Title" name="title" required maxLength={200} placeholder="What needs doing?" />
      <div className="flex flex-col gap-1.5">
        <label htmlFor="new-description" className="text-sm font-medium">
          Description
        </label>
        <textarea
          id="new-description"
          name="description"
          rows={4}
          maxLength={20000}
          className="rounded-sm border border-control bg-surface px-3 py-2 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Select label="Category" name="category" defaultValue="">
          <option value="">Not set</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
        <Select label="Priority" name="priority" defaultValue="">
          <option value="">Not set</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </Select>
        <Select label="Story points" name="story_points" defaultValue="">
          <option value="">Not set</option>
          {STORY_POINTS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </Select>
        <Select label="Assignee" name="assignee_id" defaultValue="">
          <option value="">Unassigned</option>
          {members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.display_name}
            </option>
          ))}
        </Select>
        <TextField label="Due date" name="due_date" type="date" />
        <TextField label="Labels" name="labels" placeholder="backend, database" hint="Comma-separated" />
      </div>
      <div className="flex gap-2">
        <Button type="submit" pending={create.isPending}>
          Create ticket
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}

export function splitLabels(value: string): string[] {
  return [...new Set(value.split(",").map((l) => l.trim().toLowerCase()).filter(Boolean))];
}

function toPoints(value: string): Schemas["TicketCreate"]["story_points"] {
  const points = STORY_POINTS.find((p) => String(p) === value);
  return points ?? null;
}
