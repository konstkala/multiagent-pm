import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { TeamView } from "./team-view";

export const metadata: Metadata = { title: "Team" };

export default function TeamPage() {
  return (
    <Suspense fallback={<Loading />}>
      <TeamView />
    </Suspense>
  );
}
