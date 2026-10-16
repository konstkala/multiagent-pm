import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  // The form reads ?next= and ?error= from the URL, so it renders in the browser.
  return (
    <Suspense fallback={<Loading />}>
      <SignInForm />
    </Suspense>
  );
}
