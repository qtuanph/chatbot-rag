FROM node:alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

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
