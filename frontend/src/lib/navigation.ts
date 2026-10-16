/** Only same-site paths, so a crafted ?next=https://evil.example can't send users away. */
export function safeNextPath(next: string | null): string {
  if (next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\")) {
    return next;
  }
  return "/projects";
}
