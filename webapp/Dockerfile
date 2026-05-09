# syntax=docker/dockerfile:1
FROM node:alpine AS builder
WORKDIR /app

# ── Copy package files first (most stable layer) ──
COPY package*.json ./

# ── Upgrade npm to latest, then install with persistent cache mount ──
# Cache mount persists across rebuilds — only new/changed packages downloaded
RUN --mount=type=cache,target=/root/.npm \
    npm install -g npm@latest && \
    npm ci

# ── Copy source code (changes often, comes late to avoid invalidating npm ci) ──
COPY . .

# ── Build with persistent Next.js Turbopack cache mount ──
RUN --mount=type=cache,target=/app/.next/cache \
    npm run build

# ── Runtime Stage ─────────────────────────────────────────────────────────────
FROM node:alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup -g 1001 nextapp && \
    adduser -D -u 1001 -G nextapp nextapp

# Copy only production-needed files from builder
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

RUN chown -R nextapp:nextapp /app

USER nextapp

EXPOSE 3000

CMD ["node", "server.js"]