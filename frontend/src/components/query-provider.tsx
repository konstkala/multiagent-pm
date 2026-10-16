"use client";

import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api/client";

export function QueryProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [client] = useState(
    () =>
      new QueryClient({
        // Any request that finds the session gone (expired, signed out elsewhere) goes to sign-in.
        queryCache: new QueryCache({
          onError: (error) => {
            if (error instanceof ApiError && error.status === 401) {
              const next = encodeURIComponent(window.location.pathname);
              router.replace(`/sign-in?next=${next}`);
            }
          },
        }),
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            // Retrying a 4xx can't help; retry network blips and server errors twice.
            retry: (count, error) =>
              !(error instanceof ApiError && error.status < 500) && count < 2,
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
