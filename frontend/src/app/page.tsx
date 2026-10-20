import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { HeroLines } from "@/components/hero-lines";
import { Logo } from "@/components/logo";

export const metadata: Metadata = {
  title: { absolute: "Multiagent PM · Agents prepare. People decide." },
  description:
    "Project management where AI agents classify, size and route tickets, and people make every consequential decision.",
};

// Everything claimed here is true of the code: see CLAUDE.md and ADRs 0008 to 0021.
const AGENTS = [
  {
    name: "Triage",
    text: "Reads a new ticket and proposes a category, labels, priority and story points. Spots duplicates. Asks one question when the ticket is too vague to size.",
    gate: "You accept, edit or dismiss.",
  },
  {
    name: "Assignee suggestions",
    text: "Ranks your team by skills, similar past work and current workload, then explains the top three. The model only ever sees letters and facts, never names.",
    gate: "You pick who gets the ticket.",
  },
  {
    name: "CV to profile",
    text: "Turns a CV into a skills profile, with evidence for every level, and deletes the file as soon as it has been read.",
    gate: "You review the draft before it is saved.",
  },
  {
    name: "Ticket splitting",
    text: "One model drafts sub-tickets and a stronger one reviews the draft, then the run pauses until a person decides.",
    gate: "Nothing is created until you choose.",
  },
];

const TRUST = [
  {
    title: "People decide",
    text: "Agents propose; consequential changes wait for an approval. Ticket text is untrusted input: it can never pick tools or skip a review.",
  },
  {
    title: "Cost is visible",
    text: "Every agent run has a hard $0.05 cap. Model, tokens, latency and cost are recorded per run and shown to managers.",
  },
  {
    title: "Everything is traceable",
    text: "Structured logs tied to a request or run id, audited state changes, and no secrets or ticket text in the logs.",
  },
];

const pill = "lift inline-flex items-center justify-center rounded-full font-medium";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col gap-3 p-3 md:gap-4 md:p-4">
      <header className="sticky top-3 z-20 mx-auto flex w-full max-w-6xl items-center justify-between rounded-full border border-border bg-surface/90 py-2 pr-2 pl-4 shadow-float backdrop-blur md:pl-5">
        <Link href="/" aria-label="Multiagent PM, home">
          <Logo />
        </Link>
        <nav aria-label="On this page" className="hidden items-center gap-8 text-sm md:flex">
          <a href="#agents" className="hover:text-link">
            What the agents do
          </a>
          <a href="#trust" className="hover:text-link">
            Built to be trusted
          </a>
        </nav>
        <div className="flex items-center gap-1 sm:gap-2">
          <Link href="/sign-in" className={`${pill} px-3 py-2 text-sm hover:bg-subtle sm:px-4`}>
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className={`${pill} bg-accent px-3.5 py-2 text-sm text-on-accent hover:bg-accent-strong sm:px-4`}
          >
            Get started
          </Link>
        </div>
      </header>

      <main className="flex flex-col gap-3 md:gap-4">
        <section className="hero-surface relative overflow-hidden rounded-xl px-6 py-14 md:px-14 md:py-20">
          <HeroLines className="pointer-events-none absolute inset-0 h-full w-full" />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[1fr_0.95fr]">
            <div className="flex flex-col gap-6">
              <span className="inline-flex items-center gap-2 self-start rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-semibold tracking-widest uppercase">
                <span aria-hidden="true" className="size-1.5 rounded-full bg-hero-accent" />
                AI-assisted project management
              </span>
              <h1 className="text-[2.5rem] leading-[1.02] font-semibold tracking-tight sm:text-5xl md:text-6xl">
                <span className="block">Agents prepare.</span>
                <span className="text-hero-gradient block">People decide.</span>
              </h1>
              <p className="max-w-lg text-lg text-on-hero-muted">
                Agents classify and size your tickets, build profiles from CVs and suggest who should
                take the work. You approve every consequential change.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/sign-up"
                  className={`${pill} bg-accent px-6 py-3 text-on-accent hover:bg-accent-strong`}
                >
                  Get started
                </Link>
                <Link
                  href="/sign-in"
                  className={`${pill} border border-white/40 px-6 py-3 hover:bg-white/10`}
                >
                  Sign in
                </Link>
              </div>
            </div>
            <div className="overflow-hidden rounded-xl border border-white/15 bg-surface shadow-[0_30px_80px_rgb(0_0_0/0.45)]">
              <div aria-hidden="true" className="flex gap-1.5 border-b border-border bg-subtle px-4 py-2.5">
                <span className="size-2.5 rounded-full bg-control" />
                <span className="size-2.5 rounded-full bg-control" />
                <span className="size-2.5 rounded-full bg-control" />
              </div>
              <Image
                src="/landing/ticket-split-review.webp"
                width={1000}
                height={860}
                alt="The ticket page: an agent has proposed splitting one big ticket into five sub-tickets, each with a checkbox, waiting for a manager's approval."
                loading="eager"
                fetchPriority="high"
                sizes="(min-width: 1024px) 700px, 100vw"
              />
            </div>
          </div>
        </section>

        <section id="agents" className="mx-auto w-full max-w-6xl scroll-mt-24 px-3 py-14 md:px-6 md:py-20">
          <div className="reveal flex max-w-2xl flex-col gap-3">
            <span className="text-xs font-semibold tracking-widest text-muted uppercase">
              What the agents do
            </span>
            <h2 className="text-3xl font-semibold tracking-tight text-balance md:text-5xl">
              Four agents. One rule: you approve.
            </h2>
          </div>
          <ul className="mt-10 grid gap-4 sm:grid-cols-2">
            {AGENTS.map((agent, index) => (
              <li
                key={agent.name}
                className="reveal hero-surface flex flex-col gap-4 rounded-xl p-7 md:p-8"
              >
                <span className="font-mono text-sm text-hero-accent">0{index + 1}</span>
                <h3 className="text-2xl font-semibold tracking-tight">{agent.name}</h3>
                <p className="text-on-hero-muted">{agent.text}</p>
                <p className="mt-auto flex items-center gap-2 border-t border-white/15 pt-4 text-sm font-medium">
                  <span aria-hidden="true" className="size-1.5 rounded-full bg-hero-accent" />
                  {agent.gate}
                </p>
              </li>
            ))}
          </ul>
        </section>

        <section
          id="trust"
          className="scroll-mt-24 rounded-xl border border-border bg-surface px-6 py-14 shadow-card md:px-14 md:py-20"
        >
          <div className="mx-auto max-w-6xl">
            <h2 className="reveal max-w-2xl text-3xl font-semibold tracking-tight md:text-5xl">
              Built to be trusted
            </h2>
            <ul className="mt-10 grid gap-8 md:grid-cols-3">
              {TRUST.map((fact) => (
                <li key={fact.title} className="reveal flex flex-col gap-3 border-t-2 border-accent pt-5">
                  <h3 className="text-xl font-semibold">{fact.title}</h3>
                  <p className="text-muted">{fact.text}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="hero-surface relative overflow-hidden rounded-xl px-6 py-16 text-center md:py-24">
          <HeroLines className="pointer-events-none absolute inset-0 h-full w-full" />
          <div className="relative mx-auto flex max-w-2xl flex-col items-center gap-6">
            <h2 className="text-4xl font-semibold tracking-tight text-balance md:text-6xl">
              Let the agents do the prep.
            </h2>
            <p className="text-lg text-on-hero-muted">Create a workspace in a minute. Your team decides the rest.</p>
            <Link
              href="/sign-up"
              className={`${pill} bg-accent px-7 py-3.5 text-on-accent hover:bg-accent-strong`}
            >
              Get started
            </Link>
          </div>
        </section>
      </main>

      <footer className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-4 px-3 py-6 text-sm text-muted md:px-6">
        <Logo className="text-foreground" />
        <nav aria-label="Account" className="flex gap-6">
          <Link href="/sign-in" className="hover:text-link">
            Sign in
          </Link>
          <Link href="/sign-up" className="hover:text-link">
            Create an account
          </Link>
        </nav>
      </footer>
    </div>
  );
}
