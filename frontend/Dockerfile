# syntax=docker/dockerfile:1

# Stage 1: install dependencies exactly as locked. Rebuilt only when the lockfile changes.
FROM node:25-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

# Stage 2: build. API_URL is baked into the proxy config at build time (see next.config.ts).
FROM node:25-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG API_URL=http://api:8000
ENV API_URL=$API_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 3: the image we ship: the standalone server, its static files, nothing else.
FROM node:25-slim AS runtime
# Security fixes released since the base image was built (Trivy found a fixable CRITICAL
# in perl-base). Production pins the base by digest and lets Dependabot move it.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/sign-in').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]

CMD ["node", "server.js"]
