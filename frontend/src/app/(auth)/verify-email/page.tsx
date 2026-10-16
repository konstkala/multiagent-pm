import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { VerifyEmailForm } from "./verify-email-form";

export const metadata: Metadata = { title: "Confirm email" };

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<Loading />}>
      <VerifyEmailForm />
    </Suspense>
  );
}
