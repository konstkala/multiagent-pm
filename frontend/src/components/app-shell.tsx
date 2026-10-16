"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Alert, Button, Loading } from "@/components/ui";
import { api, errorText, send } from "@/lib/api/client";
import { useMe } from "@/lib/queries";

export function AppShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [signingOut, setSigningOut] = useState(false);

  async function signOut() {
    setSigningOut(true);
    await send(api.POST("/auth/sign-out")).catch(() => undefined);
    queryClient.clear(); // drop every cached answer from this account
    router.replace("/sign-in");
  }

  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/projects" className="font-semibold tracking-tight">
            Multiagent PM
          </Link>
          {me.data ? (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-muted">{me.data.display_name}</span>
              <Button variant="secondary" onClick={signOut} pending={signingOut}>
                Sign out
              </Button>
            </div>
          ) : null}
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {me.isPending ? <Loading /> : null}
        {me.isError ? <Alert tone="error">{errorText(me.error)}</Alert> : null}
        {me.data ? children : null}
      </main>
    </div>
  );
}
