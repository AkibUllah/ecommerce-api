#!/usr/bin/env bash
# Codespaces start hook: bring up API + sweeper + PostgreSQL and seed the demo catalogue.
set -euo pipefail
cd "$(dirname "$0")/.."

# Requests arrive through the Codespaces HTTPS proxy under a *.app.github.dev host.
if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
  HOST="${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
  export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,api,${HOST}"
  export DJANGO_CSRF_TRUSTED_ORIGINS="https://${HOST}"
  export DJANGO_BEHIND_PROXY=true
fi

docker compose up -d --build

echo "waiting for the API on :8000 ..."
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:8000/health/ >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# seed_demo is idempotent (update_or_create), so it is safe on every start.
docker compose exec -T api python manage.py seed_demo

cat <<'MSG'

E-commerce API is up.
  Swagger UI:  forwarded port 8000, path /api/docs/
  Admin:       forwarded port 8000, path /admin/   (admin / admin12345)
  Demo data:   BDT catalogue with variants and stock, coupon EID10, Pathao/RedX rates
MSG
