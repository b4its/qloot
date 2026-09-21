#!/usr/bin/env bash
# ============================================================================
# qloot-ai-gateway.sh — let the QLoot backend (inside Docker) reach a host-run
# OpenAI-compatible AI gateway (e.g. http://localhost:20128/v1).
#
# Why this is needed
# ------------------
# The host firewall (ufw) sets `-P INPUT DROP`, so containers can only reach
# host ports that Docker *published*. A gateway listening on the host at some
# arbitrary port (20128 by default) is therefore unreachable from containers as
# `host.docker.internal:<port>` and every AI request times out.
#
# What this does
# --------------
# Inserts an INPUT ACCEPT rule for the AI gateway port, scoped to Docker's
# private address ranges only (never the public internet). It uses a short-lived
# `--privileged --net=host` container because the rule lives in the host kernel
# netns; no sudo password is required.
#
# Idempotent: re-running replaces its own rule instead of stacking duplicates.
# ============================================================================
set -euo pipefail

PORT="${1:-20128}"
PORT="${AI_GATEWAY_PORT:-$PORT}"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required" >&2
  exit 1
fi

echo ">> Allowing Docker networks to reach host port ${PORT} (AI gateway)…"

docker run --rm --privileged --net=host alpine sh -c "
  apk add -q iptables >/dev/null 2>&1 || true
  # Drop any previous version of our rule so re-runs stay idempotent.
  while iptables -C INPUT -s 172.16.0.0/12 -p tcp --dport ${PORT} -j ACCEPT 2>/dev/null; do
    iptables -D INPUT -s 172.16.0.0/12 -p tcp --dport ${PORT} -j ACCEPT
  done
  iptables -I INPUT -s 172.16.0.0/12 -p tcp --dport ${PORT} -j ACCEPT
  iptables -I INPUT -s 10.0.0.0/8 -p tcp --dport ${PORT} -j ACCEPT
  echo '>> firewall rule installed'
"

echo ">> Done. Verify from the backend container:"
echo "   docker compose exec backend python -c \\"
echo "     \"import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:${PORT}/v1/models').status)\""
