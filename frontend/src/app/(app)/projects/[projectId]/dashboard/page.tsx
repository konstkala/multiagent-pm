import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { DashboardView } from "./dashboard-view";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <Suspense fallback={<Loading />}>
      <DashboardView />
    </Suspense>
  );
}
