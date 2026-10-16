import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

const buttonStyles = {
  primary: "bg-accent text-white hover:bg-accent-strong disabled:opacity-60",
  secondary:
    "bg-surface text-foreground border border-border hover:bg-background disabled:opacity-60",
  danger: "bg-surface text-danger border border-border hover:bg-red-50 disabled:opacity-60",
} as const;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof buttonStyles;
  pending?: boolean;
};

export function Button({
  variant = "primary",
  pending = false,
  disabled,
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || pending}
      aria-busy={pending}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${buttonStyles[variant]} ${className}`}
    >
      {pending ? "Working…" : children}
    </button>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string };

export function TextField({ label, hint, id, name, ...props }: FieldProps) {
  const fieldId = id ?? name;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={fieldId}
        name={name}
        {...props}
        className="rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
      />
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { label: string };

export function Select({ label, id, name, children, ...props }: SelectProps) {
  const fieldId = id ?? name;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-sm font-medium">
        {label}
      </label>
      <select
        id={fieldId}
        name={name}
        {...props}
        className="rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
      >
        {children}
      </select>
    </div>
  );
}

export function Alert({ tone, children }: { tone: "error" | "success" | "info"; children: ReactNode }) {
  const tones = {
    error: "border-red-200 bg-red-50 text-danger",
    success: "border-green-200 bg-green-50 text-success",
    info: "border-border bg-background text-muted",
  };
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-md border px-3 py-2 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-border bg-surface">
      {title ? (
        <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          {actions}
        </header>
      ) : null}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full border border-border bg-background px-2 py-0.5 text-xs font-medium text-muted">
      {children}
    </span>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="text-sm text-muted">{label}</p>;
}
