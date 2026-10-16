import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "pm_session";

/**
 * Optimistic check only: no cookie means certainly signed out, so skip a page that would just
 * bounce. Whether a cookie is valid is decided by the API on every request.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const signIn = new URL("/sign-in", request.url);
  signIn.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(signIn);
}

export const config = { matcher: ["/projects/:path*"] };
