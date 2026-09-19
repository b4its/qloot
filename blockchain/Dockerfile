# Hardhat toolbox image for compile/deploy/verify/transfer operations.
# The private key is provided at runtime via env, never baked into the image.
FROM node:20-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .

# Compile at build time so artifacts are ready for the toolbox.
RUN npx hardhat compile || true

# Non-root user.
RUN useradd --create-home --uid 10001 hardhat || true
USER 10001

ENTRYPOINT ["npx", "hardhat"]
CMD ["--help"]
