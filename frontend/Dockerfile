# Portal frontend (Next.js) for AWS ECS Fargate
# Build with: docker build --platform linux/amd64 --build-arg NEXT_PUBLIC_API_URL=http://... -t frontend .
FROM node:20-alpine AS builder

WORKDIR /app

# Build-time API URL (Django portal); set by deploy script
ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
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
