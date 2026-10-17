import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { ProfileView } from "./profile-view";

export const metadata: Metadata = { title: "Profile" };

export default function ProfilePage() {
  return (
    <Suspense fallback={<Loading />}>
      <ProfileView />
    </Suspense>
  );
}
