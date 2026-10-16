import { Suspense } from "react";

import { ProjectHeader } from "@/components/project-header";
import { Loading } from "@/components/ui";

export default function ProjectLayout({ children }: LayoutProps<"/projects/[projectId]">) {
  return (
    <div className="flex flex-col gap-6">
      {/* The header reads the project id from the URL, so it renders in the browser. */}
      <Suspense fallback={<Loading />}>
        <ProjectHeader />
      </Suspense>
      {children}
    </div>
  );
}
