import Link from "next/link";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <Link href="/" className="text-center text-lg font-semibold tracking-tight">
          Multiagent PM
        </Link>
        <div className="rounded-sm border border-border bg-surface p-8">{children}</div>
      </div>
    </main>
  );
}
