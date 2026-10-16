import type { NextConfig } from "next";

// Where the FastAPI backend is, as seen from this Next.js server. Read at build time: the Docker
// image bakes in http://api:8000, local development uses the default.
const apiUrl = process.env.API_URL ?? "http://localhost:8000";

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" }, // no clickjacking via iframes
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  output: "standalone", // a self-contained server for the Docker image
  poweredByHeader: false,
  experimental: {
    // The proxy's default 10 MB cut-off would break uploads just over 10 MB with a bare 500.
    // Slightly above the API's own 10 MB limit, so the API decides and answers with a clear 413.
    proxyClientMaxBodySize: "12mb",
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The browser only ever talks to this origin; /api is proxied to FastAPI. The session cookie
  // stays first-party and no CORS is needed.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      // These URLs carry one-time tokens; never leak them to other sites via Referer.
      {
        source: "/(verify-email|reset-password)",
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      },
    ];
  },
};

export default nextConfig;
