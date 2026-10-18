"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Avatar } from "@/components/tickets";
import { Alert, Button } from "@/components/ui";
import { api, call, errorText, send, type Schemas } from "@/lib/api/client";
import { keys } from "@/lib/queries";
import { formatTime } from "@/lib/tickets";

import type { TicketContext } from "./ticket-detail";

type Comment = Schemas["CommentRead"];

/** The box at the end of the timeline. */
export function CommentForm({ context }: { context: TicketContext }) {
  const { ticket } = context;
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const add = useMutation({
    mutationFn: (text: string) =>
      call(
        api.POST("/tickets/{ticket_id}/comments", {
          params: { path: { ticket_id: ticket.id } },
          body: { body: text },
        }),
      ),
    onSuccess: async () => {
      setBody("");
      await queryClient.invalidateQueries({ queryKey: keys.comments(ticket.id) });
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (body.trim()) add.mutate(body.trim());
  }

  return (
    <section className="flex flex-col gap-3">
      <form onSubmit={onSubmit} className="flex flex-col gap-2">
        <label htmlFor="new-comment" className="sr-only">
          Add a comment
        </label>
        <textarea
          id="new-comment"
          value={body}
          rows={3}
          maxLength={10000}
          placeholder="Add a comment…"
          onChange={(event) => setBody(event.target.value)}
          className="rounded-sm border border-control bg-surface px-3 py-2 text-sm outline-none focus:border-ring"
        />
        {add.isError ? <Alert tone="error">{errorText(add.error)}</Alert> : null}
        <div>
          <Button type="submit" disabled={!body.trim()} pending={add.isPending}>
            Comment
          </Button>
        </div>
      </form>
    </section>
  );
}

export function CommentItem({ comment, context }: { comment: Comment; context: TicketContext }) {
  const { ticket, me, isManager } = context;
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(comment.body);
  const isMine = comment.author_id === me.id;
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.comments(ticket.id) });
  const path = { comment_id: comment.id };

  const edit = useMutation({
    mutationFn: () => call(api.PATCH("/comments/{comment_id}", { params: { path }, body: { body: text } })),
    onSuccess: async () => {
      setEditing(false);
      await refresh();
    },
  });
  const remove = useMutation({
    mutationFn: () => send(api.DELETE("/comments/{comment_id}", { params: { path } })),
    onSuccess: refresh,
  });
  const author = comment.author_name ?? "Deleted user";

  return (
    <li className="flex gap-3">
      <Avatar name={author} />
      <div className="flex min-w-0 flex-1 flex-col gap-1 rounded-sm border border-border bg-surface p-3">
        <div className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
          <span className="font-medium text-foreground">{author}</span>
          <span>{formatTime(comment.created_at)}</span>
          {comment.edited_at ? <span>(edited)</span> : null}
          <span className="ml-auto flex gap-3">
            {isMine && !editing ? (
              <button type="button" onClick={() => setEditing(true)} className="hover:text-link">
                Edit
              </button>
            ) : null}
            {isMine || isManager ? (
              <button
                type="button"
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
                className="hover:text-danger"
              >
                Delete
              </button>
            ) : null}
          </span>
        </div>
        {editing ? (
          <div className="flex flex-col gap-2">
            <textarea
              aria-label="Edit comment"
              value={text}
              rows={3}
              maxLength={10000}
              onChange={(event) => setText(event.target.value)}
              className="rounded-sm border border-control bg-surface px-3 py-2 text-sm outline-none focus:border-ring"
            />
            <div className="flex gap-2">
              <Button disabled={!text.trim()} pending={edit.isPending} onClick={() => edit.mutate()}>
                Save
              </Button>
              <Button variant="secondary" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <p className="whitespace-pre-wrap break-words text-sm">{comment.body}</p>
        )}
        {edit.isError || remove.isError ? (
          <Alert tone="error">{errorText(edit.error ?? remove.error)}</Alert>
        ) : null}
      </div>
    </li>
  );
}
