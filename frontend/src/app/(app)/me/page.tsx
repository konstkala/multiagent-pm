import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { MyWorkView } from "./my-work-view";

export const metadata: Metadata = { title: "My work" };

export default function MyWorkPage() {
  return (
    <Suspense fallback={<Loading />}>
      <MyWorkView />
    </Suspense>
  );
}
