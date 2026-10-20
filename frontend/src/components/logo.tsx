/** The mark (three connected nodes: the agents) and the wordmark. The text follows the current colour. */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 font-semibold tracking-tight ${className}`}>
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
        <rect width="32" height="32" rx="9" fill="var(--accent)" />
        <path
          d="M9 21 16 10l7 11"
          fill="none"
          stroke="#fff"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="9" cy="21" r="2.7" fill="#fff" />
        <circle cx="16" cy="10" r="2.7" fill="#fff" />
        <circle cx="23" cy="21" r="2.7" fill="#fff" />
      </svg>
      Multiagent PM
    </span>
  );
}
