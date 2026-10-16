import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/ui";

import { ProjectView } from "./project-view";

export const metadata: Metadata = { title: "Project" };

export default function ProjectPage() {
  // The project id comes from the URL, so the view renders in the browser.
  return (
    <Suspense fallback={<Loading />}>
      <ProjectView />
    </Suspense>
  );
}
