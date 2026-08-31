# ── Stage 1: dipendenze ────────────────────────────────────────────────────
FROM node:22-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json* ./
# `npm ci` se c'e' il lockfile, altrimenti install (primo avvio del progetto).
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# ── Stage 2: build / dev ───────────────────────────────────────────────────
FROM node:22-alpine

RUN apk add --no-cache rsync

WORKDIR /app
ENV NODE_ENV=production \
    ASTRO_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 4321
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["build"]
