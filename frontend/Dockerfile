# ── Stage 1: install production dependencies ──────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /build

COPY package.json package-lock.json ./
# ci enforces the lockfile — reproducible installs only
RUN npm ci --omit=dev

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM node:20-alpine AS runtime

# node:alpine ships with a built-in "node" user (uid 1000)
WORKDIR /app

# Copy node_modules from builder (no dev deps)
COPY --from=builder /build/node_modules ./node_modules

# Copy application code
COPY app.js .
COPY views/ ./views/

USER node

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/health || exit 1

CMD ["node", "app.js"]
