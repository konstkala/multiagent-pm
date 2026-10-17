import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { InviteView } from "./invite-view";

export const metadata: Metadata = { title: "Invitation" };

export default function InvitePage() {
  return (
    <Suspense fallback={<Loading />}>
      <InviteView />
    </Suspense>
  );
}
