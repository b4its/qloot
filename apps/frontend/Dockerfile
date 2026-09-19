# QLoot frontend (SvelteKit + adapter-node).
FROM node:20-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .
ARG PUBLIC_API_URL=http://localhost:8000
ENV PUBLIC_API_URL=$PUBLIC_API_URL
RUN npm run build

# --- runtime ---------------------------------------------------------------
FROM node:20-bookworm-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0

# Copy the adapter-node output and production deps only.
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules

RUN useradd --create-home --uid 10002 qloot || true
USER 10002

EXPOSE 3000
CMD ["node", "build"]
