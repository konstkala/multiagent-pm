import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { Board } from "./board";

export const metadata: Metadata = { title: "Board" };

export default function BoardPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Board />
    </Suspense>
  );
}
