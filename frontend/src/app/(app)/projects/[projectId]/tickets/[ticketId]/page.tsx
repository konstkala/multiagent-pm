import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { TicketDetail } from "./ticket-detail";

export const metadata: Metadata = { title: "Ticket" };

export default function TicketPage() {
  return (
    <Suspense fallback={<Loading />}>
      <TicketDetail />
    </Suspense>
  );
}
