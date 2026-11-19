#!/usr/bin/env bash
# Recova-H2S Standalone VPS Deployment Script
# Usage:
#   bash deploy/vps/setup-vps.sh [--domain h2s.recovahq.com] [--ssl] [--force-nginx]
#
# Designed to run safely alongside existing VPS stacks (e.g., /var/www/recova/production
# and /etc/nginx/sites-available/recova) without touching existing Nginx configs, containers,
# volumes, networks, or host ports.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.vps.yml"
ENV_TEMPLATE="${SCRIPT_DIR}/.env.vps.example"
ENV_FILE="${REPO_ROOT}/.env.vps"
NGINX_TEMPLATE="${SCRIPT_DIR}/nginx/h2s.recovahq.com.conf"

DOMAIN="h2s.recovahq.com"
ENABLE_SSL=false
FORCE_NGINX=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="${2:?--domain requires a value}"
      shift 2
      ;;
    --ssl)
      ENABLE_SSL=true
      shift
      ;;
    --force-nginx)
      FORCE_NGINX=true
      shift
      ;;
    -h|--help)
      echo "Usage: bash deploy/vps/setup-vps.sh [--domain h2s.recovahq.com] [--ssl] [--force-nginx]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: Required command '$1' is not installed or not in PATH." >&2
    exit 1
  fi
}

require_cmd docker
require_cmd python3

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: 'docker compose' plugin is required." >&2
  exit 1
fi

cd "${REPO_ROOT}"

# 1. Create .env.vps with strong generated secrets on first run
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "==> Creating ${ENV_FILE} with generated production secrets..."
  cp "${ENV_TEMPLATE}" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"

  POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  FIELD_ENCRYPTION_KEY="$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"

  python3 - "${ENV_FILE}" "${DOMAIN}" "${POSTGRES_PASSWORD}" "${SECRET_KEY}" "${FIELD_ENCRYPTION_KEY}" <<'PY'
import pathlib, sys

env_path = pathlib.Path(sys.argv[1])
domain, pg_pass, secret_key, fernet_key = sys.argv[2:6]
text = env_path.read_text(encoding="utf-8")
text = text.replace("__GENERATE_POSTGRES_PASSWORD__", pg_pass)
text = text.replace("__GENERATE_SECRET_KEY__", secret_key)
text = text.replace("__GENERATE_FIELD_ENCRYPTION_KEY__", fernet_key)
text = text.replace("h2s.recovahq.com", domain)
env_path.write_text(text, encoding="utf-8")
PY
  echo "    Created ${ENV_FILE} (mode 600)."
else
  echo "==> Using existing ${ENV_FILE} (preserving secrets)."
fi

# Read H2S_FRONTEND_PORT and H2S_BACKEND_PORT safely from .env.vps
H2S_FRONTEND_PORT="$(grep -E '^H2S_FRONTEND_PORT=' "${ENV_FILE}" | tail -n1 | cut -d'=' -f2- || true)"
H2S_BACKEND_PORT="$(grep -E '^H2S_BACKEND_PORT=' "${ENV_FILE}" | tail -n1 | cut -d'=' -f2- || true)"
H2S_FRONTEND_PORT="${H2S_FRONTEND_PORT:-3810}"
H2S_BACKEND_PORT="${H2S_BACKEND_PORT:-8810}"

# 2. Guard against accidental host port collisions with existing VPS services
check_port_available() {
  local port="$1"
  local expected_container="$2"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn | awk '{print $4}' | grep -qE "(^|:)${port}$"; then
      if ! docker ps --format '{{.Names}}' | grep -qx "${expected_container}"; then
        echo "ERROR: Port ${port} is already in use by another service on this VPS!" >&2
        echo "Update H2S_BACKEND_PORT / H2S_FRONTEND_PORT in ${ENV_FILE} and re-run." >&2
        exit 1
      fi
    fi
  fi
}

check_port_available "${H2S_BACKEND_PORT}" "recova-h2s-backend"
check_port_available "${H2S_FRONTEND_PORT}" "recova-h2s-frontend"

# 3. Build & start standalone Docker Compose stack (recova-h2s)
echo "==> Building and starting recova-h2s containers (backend 127.0.0.1:${H2S_BACKEND_PORT}, frontend 127.0.0.1:${H2S_FRONTEND_PORT})..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --build --remove-orphans

echo "==> Waiting for backend readiness (/readyz)..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${H2S_BACKEND_PORT}/readyz" >/dev/null 2>&1; then
    echo "    Backend ready!"
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: Backend did not become ready in time. Inspect logs:" >&2
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs --tail=50 backend
    exit 1
  fi
  sleep 2
done

echo "==> Waiting for frontend readiness..."
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${H2S_FRONTEND_PORT}"; then
    echo "    Frontend ready!"
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: Frontend did not become ready in time. Inspect logs:" >&2
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs --tail=50 frontend
    exit 1
  fi
  sleep 2
done

# 4. Install dedicated Nginx site without modifying any existing site configs
NGINX_AVAILABLE="/etc/nginx/sites-available/${DOMAIN}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"

if command -v nginx >/dev/null 2>&1; then
  if [[ ! -f "${NGINX_AVAILABLE}" || "${FORCE_NGINX}" == "true" ]]; then
    echo "==> Installing Nginx config at ${NGINX_AVAILABLE}..."
    TMP_CONF="$(mktemp)"
    sed \
      -e "s|__H2S_DOMAIN__|${DOMAIN}|g" \
      -e "s|__H2S_BACKEND_PORT__|${H2S_BACKEND_PORT}|g" \
      -e "s|__H2S_FRONTEND_PORT__|${H2S_FRONTEND_PORT}|g" \
      "${NGINX_TEMPLATE}" > "${TMP_CONF}"
    sudo cp "${TMP_CONF}" "${NGINX_AVAILABLE}"
    rm -f "${TMP_CONF}"
  else
    echo "==> Keeping existing ${NGINX_AVAILABLE} (preserving any Certbot SSL rules; pass --force-nginx to overwrite)."
  fi

  sudo ln -sf "${NGINX_AVAILABLE}" "${NGINX_ENABLED}"
  sudo nginx -t
  sudo systemctl reload nginx
  echo "    Nginx validated and reloaded cleanly."
else
  echo "WARNING: nginx not found in PATH. Skipping Nginx setup."
fi

# 5. Provision SSL certificate with Certbot when --ssl is passed
if [[ "${ENABLE_SSL}" == "true" ]]; then
  require_cmd certbot
  if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
    echo "==> SSL certificate already exists for ${DOMAIN}."
  else
    echo "==> Requesting Let's Encrypt SSL certificate for ${DOMAIN}..."
    sudo certbot --nginx -d "${DOMAIN}" --redirect
  fi
fi

echo ""
echo "================================================================="
echo " Recova-H2S Deployment Complete"
echo "================================================================="
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps
echo ""
echo "Local loopback checks:"
echo "  curl -s http://127.0.0.1:${H2S_BACKEND_PORT}/readyz"
echo "  curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:${H2S_FRONTEND_PORT}"
if [[ "${ENABLE_SSL}" == "false" ]]; then
  echo ""
  echo "Once DNS A record for ${DOMAIN} points to this VPS, issue SSL:"
  echo "  sudo certbot --nginx -d ${DOMAIN} --redirect"
fi
