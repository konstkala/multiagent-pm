import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { QueryProvider } from "@/components/query-provider";
import { Loading } from "@/components/ui";

// Everything in (app) is per-user, so it loads in the browser after the static shell arrives.
export default function SignedInLayout({ children }: LayoutProps<"/">) {
  return (
    <QueryProvider>
      <Suspense fallback={<Loading />}>
        <AppShell>{children}</AppShell>
      </Suspense>
    </QueryProvider>
  );
}
