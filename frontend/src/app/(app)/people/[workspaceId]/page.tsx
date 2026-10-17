import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { PeopleView } from "./people-view";

export const metadata: Metadata = { title: "People" };

export default function PeoplePage() {
  return (
    <Suspense fallback={<Loading />}>
      <PeopleView />
    </Suspense>
  );
}
