import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { CalendarView } from "./calendar-view";

export const metadata: Metadata = { title: "Calendar" };

export default function CalendarPage() {
  return (
    <Suspense fallback={<Loading />}>
      <CalendarView />
    </Suspense>
  );
}
