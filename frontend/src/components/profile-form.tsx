"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";

export type ProfileValues = Schemas["ProfileWrite"];
export type SkillRow = { name: string; level: number; evidence?: string };

export const LEVEL_LABEL: Record<number, string> = {
  1: "1 · mentioned",
  2: "2 · basic",
  3: "3 · working",
  4: "4 · strong",
  5: "5 · expert",
};

type Props = {
  initial: { headline: string; summary: string; years_experience: number | null; skills: SkillRow[] };
  submitLabel: string;
  pending: boolean;
  onSubmit: (values: ProfileValues) => void;
  secondary?: ReactNode;
};

/** Edits a profile. Shows the agent's evidence per skill when there is some. */
export function ProfileForm({ initial, submitLabel, pending, onSubmit, secondary }: Props) {
  const [headline, setHeadline] = useState(initial.headline);
  const [summary, setSummary] = useState(initial.summary);
  const [years, setYears] = useState(initial.years_experience?.toString() ?? "");
  const [skills, setSkills] = useState<SkillRow[]>(initial.skills);

  function update(index: number, change: Partial<SkillRow>) {
    setSkills((rows) => rows.map((row, i) => (i === index ? { ...row, ...change } : row)));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedYears = Number.parseInt(years, 10);
    onSubmit({
      headline: headline.trim(),
      summary: summary.trim(),
      years_experience: Number.isNaN(parsedYears) ? null : parsedYears,
      skills: skills
        .filter((s) => s.name.trim())
        .map((s) => ({ name: s.name.trim(), level: s.level })),
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
        <Labelled label="Headline" htmlFor="profile-headline">
          <input
            id="profile-headline"
            value={headline}
            maxLength={150}
            onChange={(e) => setHeadline(e.target.value)}
            className={inputClass}
          />
        </Labelled>
        <Labelled label="Years of experience" htmlFor="profile-years">
          <input
            id="profile-years"
            type="number"
            min={0}
            max={60}
            value={years}
            onChange={(e) => setYears(e.target.value)}
            className={inputClass}
          />
        </Labelled>
      </div>
      <Labelled label="Summary" htmlFor="profile-summary">
        <textarea
          id="profile-summary"
          rows={3}
          maxLength={5000}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          className={inputClass}
        />
      </Labelled>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium">Skills</legend>
        {skills.map((skill, index) => (
          <div key={index} className="flex flex-col gap-1 rounded-md border border-border p-2">
            <div className="flex gap-2">
              <input
                aria-label="Skill name"
                value={skill.name}
                maxLength={60}
                onChange={(e) => update(index, { name: e.target.value })}
                className={`${inputClass} min-w-0 flex-1`}
              />
              <select
                aria-label={`Level of ${skill.name || "skill"}`}
                value={skill.level}
                onChange={(e) => update(index, { level: Number(e.target.value) })}
                className={inputClass}
              >
                {[1, 2, 3, 4, 5].map((level) => (
                  <option key={level} value={level}>
                    {LEVEL_LABEL[level]}
                  </option>
                ))}
              </select>
              <button
                type="button"
                aria-label={`Remove ${skill.name || "skill"}`}
                onClick={() => setSkills((rows) => rows.filter((_, i) => i !== index))}
                className="px-2 text-xs text-muted hover:text-danger"
              >
                Remove
              </button>
            </div>
            {skill.evidence ? <p className="text-xs text-muted">Evidence: {skill.evidence}</p> : null}
          </div>
        ))}
        <div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => setSkills((rows) => [...rows, { name: "", level: 3 }])}
          >
            Add skill
          </Button>
        </div>
      </fieldset>

      <div className="flex gap-2">
        <Button type="submit" pending={pending}>
          {submitLabel}
        </Button>
        {secondary}
      </div>
    </form>
  );
}

const inputClass =
  "rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent";

function Labelled({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}
