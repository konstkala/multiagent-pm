import Link from "next/link";

import { HeroLines } from "@/components/hero-lines";
import { Logo } from "@/components/logo";

const TRUST = ["Every change needs a person's approval", "A $0.05 cap on every agent run", "Every action is logged"];

/** Sign-in and friends: a navy hero beside the form on desktop, a compact banner above it on a phone. */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex flex-1 flex-col gap-3 p-3 lg:grid lg:grid-cols-[1.05fr_1fr] lg:gap-4 lg:p-4">
      <section className="hero-surface relative flex flex-col justify-between gap-10 overflow-hidden rounded-xl p-6 lg:p-12">
        <HeroLines className="pointer-events-none absolute inset-0 h-full w-full" />
        <Link href="/" className="relative self-start">
          <Logo />
        </Link>
        <div className="relative flex flex-col gap-5">
          <span className="inline-flex items-center gap-2 self-start rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-semibold tracking-widest uppercase">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-hero-accent" />
            AI-assisted project management
          </span>
          <p className="text-4xl leading-[1.05] font-semibold tracking-tight lg:text-6xl">
            <span className="block">Agents prepare.</span>
            <span className="text-hero-gradient block">People decide.</span>
          </p>
          <p className="hidden max-w-md text-on-hero-muted lg:block">
            Agents classify and size tickets, build profiles from CVs and suggest who should take the
            work. You make every consequential decision.
          </p>
        </div>
        <ul className="relative hidden flex-col gap-2 text-sm text-on-hero-muted lg:flex">
          {TRUST.map((fact) => (
            <li key={fact} className="flex items-center gap-2">
              <span aria-hidden="true" className="size-1.5 rounded-full bg-hero-accent" />
              {fact}
            </li>
          ))}
        </ul>
      </section>
      <div className="flex items-center justify-center rounded-xl border border-border bg-surface px-4 py-10 shadow-card lg:px-12">
        {/* The pages bring their own h1: one place makes them all bigger here. */}
        <div className="w-full max-w-sm [&_h1]:text-3xl [&_h1]:font-semibold [&_h1]:tracking-tight">
          {children}
        </div>
      </div>
    </main>
  );
}
