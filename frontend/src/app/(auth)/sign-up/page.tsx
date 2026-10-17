import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { SignUpForm } from "./sign-up-form";

export const metadata: Metadata = { title: "Create account" };

export default function SignUpPage() {
  // An invitation link may pre-fill ?email=, so the form renders in the browser.
  return (
    <Suspense fallback={<Loading />}>
      <SignUpForm />
    </Suspense>
  );
}
