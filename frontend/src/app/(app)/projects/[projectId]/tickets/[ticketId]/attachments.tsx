"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type ChangeEvent } from "react";

import { Alert, Loading } from "@/components/ui";
import { api, call, errorText, send, type Schemas } from "@/lib/api/client";
import { keys, useAttachments } from "@/lib/queries";
import { formatBytes, formatTime } from "@/lib/tickets";

import type { TicketContext } from "./ticket-detail";

type Attachment = Schemas["AttachmentRead"];

const MAX_BYTES = 10 * 1024 * 1024; // the API enforces the same limit
const ACCEPT = ".png,.jpg,.jpeg,.gif,.webp,.pdf,.zip,.docx,.xlsx,.pptx,.txt,.log,.md,.csv,.json";
const IMAGE = /^image\/(png|jpeg|gif|webp)$/;

export function Attachments({ context }: { context: TicketContext }) {
  const { ticket, me, isManager } = context;
  const attachments = useAttachments(ticket.id);
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [tooBig, setTooBig] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.attachments(ticket.id) });

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return call(
        api.POST("/tickets/{ticket_id}/attachments", {
          params: { path: { ticket_id: ticket.id } },
          body: { file: file.name },
          bodySerializer: () => form, // multipart; the browser sets the boundary header
        }),
      );
    },
    onSettled: async () => {
      if (input.current) input.current.value = "";
      await refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (attachmentId: string) =>
      send(api.DELETE("/attachments/{attachment_id}", { params: { path: { attachment_id: attachmentId } } })),
    onSuccess: refresh,
  });

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setTooBig(`${file.name} is ${formatBytes(file.size)}; files can be at most 10 MB.`);
      event.target.value = "";
      return;
    }
    setTooBig(null);
    upload.mutate(file);
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">
          Files{attachments.data ? ` (${attachments.data.length})` : ""}
        </h2>
        <label className="cursor-pointer text-xs font-medium text-link hover:underline">
          {upload.isPending ? "Uploading…" : "Attach a file"}
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            onChange={onPick}
            disabled={upload.isPending}
            className="sr-only"
          />
        </label>
      </div>
      {tooBig ? <Alert tone="error">{tooBig}</Alert> : null}
      {upload.isError ? <Alert tone="error">{errorText(upload.error)}</Alert> : null}
      {remove.isError ? <Alert tone="error">{errorText(remove.error)}</Alert> : null}
      {attachments.isPending ? <Loading /> : null}
      {attachments.data?.length === 0 ? (
        <p className="text-sm text-muted">
          No files yet. Screenshots, logs or documents that show the work is done go here.
        </p>
      ) : null}
      <ul className="grid gap-2 sm:grid-cols-2">
        {attachments.data?.map((file) => (
          <FileRow
            key={file.id}
            file={file}
            canDelete={isManager || file.uploader_id === me.id}
            onDelete={() => remove.mutate(file.id)}
          />
        ))}
      </ul>
    </section>
  );
}

function FileRow({
  file,
  canDelete,
  onDelete,
}: {
  file: Attachment;
  canDelete: boolean;
  onDelete: () => void;
}) {
  const href = `/api/attachments/${file.id}/download`;
  return (
    <li className="flex items-center gap-3 rounded-sm border border-border bg-surface p-2">
      {IMAGE.test(file.content_type) ? (
        // eslint-disable-next-line @next/next/no-img-element -- private, auth-checked file; not optimisable
        <img
          src={`${href}?inline=true`}
          alt={file.filename}
          className="size-12 shrink-0 rounded object-cover"
        />
      ) : (
        <span className="flex size-12 shrink-0 items-center justify-center rounded bg-subtle text-[10px] font-semibold uppercase text-muted">
          {file.filename.split(".").pop()}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <a href={href} className="block truncate text-sm font-medium hover:text-link hover:underline">
          {file.filename}
        </a>
        <p className="truncate text-xs text-muted">
          {formatBytes(file.size_bytes)} · {file.uploader_name ?? "Deleted user"} ·{" "}
          {formatTime(file.created_at)}
        </p>
      </div>
      {canDelete ? (
        <button
          type="button"
          onClick={onDelete}
          aria-label={`Delete ${file.filename}`}
          className="px-1 text-xs text-muted hover:text-danger"
        >
          Delete
        </button>
      ) : null}
    </li>
  );
}
