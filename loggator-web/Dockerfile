FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
# next-auth beta currently has a peer range that doesn't include Next 16.
# We intentionally accept the peer mismatch for now.
RUN npm ci --legacy-peer-deps

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Browser-facing URLs (baked at build). Override via compose build.args for other hosts.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/live
# Auth UI flags are inlined into the client bundle at build time (runtime env is too late).
ARG NEXT_PUBLIC_AUTH_ALLOW_TOKEN=true
ARG NEXT_PUBLIC_AUTH_SSO_ENABLED=false
ARG NEXT_PUBLIC_AUTH_END_SESSION_URL=
ARG NEXT_PUBLIC_AUTH_POST_LOGOUT_REDIRECT_URI=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_AUTH_ALLOW_TOKEN=$NEXT_PUBLIC_AUTH_ALLOW_TOKEN
ENV NEXT_PUBLIC_AUTH_SSO_ENABLED=$NEXT_PUBLIC_AUTH_SSO_ENABLED
ENV NEXT_PUBLIC_AUTH_END_SESSION_URL=$NEXT_PUBLIC_AUTH_END_SESSION_URL
ENV NEXT_PUBLIC_AUTH_POST_LOGOUT_REDIRECT_URI=$NEXT_PUBLIC_AUTH_POST_LOGOUT_REDIRECT_URI
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 3000
CMD ["node", "server.js"]
