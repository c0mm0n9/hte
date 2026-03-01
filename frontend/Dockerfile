# Portal frontend (Next.js) for AWS ECS Fargate
# Build with: docker build --platform linux/amd64 --build-arg NEXT_PUBLIC_API_URL=http://... -t frontend .
FROM node:20-alpine AS builder

WORKDIR /app

# Build-time: leave NEXT_PUBLIC_API_URL empty so browser uses same-origin /api/portal/* (proxy uses DJANGO_API_URL at runtime)
ARG NEXT_PUBLIC_API_URL=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
