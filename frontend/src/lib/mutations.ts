"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, call, type Schemas, type Ticket } from "@/lib/api/client";
import { keys } from "@/lib/queries";

export type TicketChanges = Schemas["TicketUpdate"];

/** PATCH a ticket, then refresh the ticket and every list it can appear in. */
export function useUpdateTicket(ticket: Pick<Ticket, "id" | "project_id">) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (changes: TicketChanges) =>
      call(
        api.PATCH("/tickets/{ticket_id}", {
          params: { path: { ticket_id: ticket.id } },
          body: changes,
        }),
      ),
    onSuccess: async (updated) => {
      queryClient.setQueryData(keys.ticket(ticket.id), updated);
      await queryClient.invalidateQueries({ queryKey: keys.ticketLists(ticket.project_id) });
      await queryClient.invalidateQueries({ queryKey: keys.similar(ticket.id) });
    },
  });
}
