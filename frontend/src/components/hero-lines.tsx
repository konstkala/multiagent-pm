/**
 * Flowing lines for the navy hero: the agents' work fanning out from one point. Pure SVG, drawn
 * twice (a faint solid line, and a brighter dashed one that drifts), so the motion is only a
 * stroke offset. The animation classes live in globals.css and turn off for reduced motion.
 */
const PATHS = [
  "M-20 250 C 200 250, 380 200, 820 70",
  "M-20 255 C 220 255, 400 235, 820 160",
  "M-20 258 C 260 258, 440 290, 820 300",
  "M-20 262 C 240 262, 420 270, 820 250",
  "M-20 265 C 240 270, 420 310, 820 340",
  "M-20 270 C 220 280, 400 360, 820 430",
];

const DOTS: [number, number, number][] = [
  [520, 190, 0],
  [610, 262, 1.2],
  [700, 332, 2.4],
  [470, 300, 0.6],
  [330, 252, 1.8],
];

// The lines fade out toward the left, where the hero's text sits, so they never run through it.
const FADE = "linear-gradient(to right, transparent 25%, #000 80%)";

export function HeroLines({ className = "" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 800 500"
      preserveAspectRatio="xMaxYMid slice"
      className={`text-[#6ea8ff] ${className}`}
      style={{ maskImage: FADE, WebkitMaskImage: FADE }}
    >
      <g fill="none" stroke="currentColor" strokeLinecap="round">
        {PATHS.map((d) => (
          <g key={d}>
            <path d={d} strokeWidth="1" opacity="0.28" />
            <path d={d} strokeWidth="1.6" opacity="0.7" className="hero-line" />
          </g>
        ))}
      </g>
      <g fill="currentColor">
        {DOTS.map(([cx, cy, delay]) => (
          <circle
            key={`${cx}-${cy}`}
            cx={cx}
            cy={cy}
            r="2.6"
            className="hero-dot"
            style={{ animationDelay: `${delay}s` }}
          />
        ))}
      </g>
    </svg>
  );
}
