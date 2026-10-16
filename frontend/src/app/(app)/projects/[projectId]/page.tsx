import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { TicketsList } from "./tickets-list";

export const metadata: Metadata = { title: "Tickets" };

export default function ProjectTicketsPage() {
  // Filters come from the URL, so the list renders in the browser.
  return (
    <Suspense fallback={<Loading />}>
      <TicketsList />
    </Suspense>
  );
}
