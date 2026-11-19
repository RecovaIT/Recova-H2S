# Standalone VPS Deployment Guide (`h2s.recovahq.com`)

This guide deploys **Recova-H2S** as an isolated Docker + Nginx + Certbot stack on a VPS that already hosts another production stack (such as `/var/www/recova/production` and `/etc/nginx/sites-available/recova`).

---

## Isolation Guarantees (Zero Conflict With Existing VPS Services)

| Resource | Existing Production Stack (`/var/www/recova/production`) | Recova-H2S Stack (`/var/www/recova-h2s`) |
| --- | --- | --- |
| **Directory** | `/var/www/recova/production` | `/var/www/recova-h2s` |
| **Compose Project** | `docker-compose.prod.yml` | `docker-compose.vps.yml` (`name: recova-h2s`) |
| **Containers** | Existing production containers | `recova-h2s-postgres`, `recova-h2s-backend`, `recova-h2s-worker`, `recova-h2s-frontend` |
| **Docker Network** | Existing production network | `recova_h2s_net` |
| **Database Volume** | Existing production DB/volume | `recova_h2s_pgdata` (PostgreSQL `5432` stays internal-only, **not** bound to host) |
| **Host Loopback Ports** | Existing ports (`3000`, `8000`, etc.) | `127.0.0.1:8810` (backend), `127.0.0.1:3810` (frontend) — configurable in `.env.vps` |
| **Nginx Config** | `/etc/nginx/sites-available/recova` (untouched) | `/etc/nginx/sites-available/h2s.recovahq.com` |
| **Cookies / Origin** | Existing subdomains (`api.recovahq.com`, `admin...`) | Host-only cookies scoped strictly to `h2s.recovahq.com` |

---

## 1. Create DNS Record First

In your DNS provider for `recovahq.com`, create an **A** record pointing to your VPS public IPv4 address:

- **Type:** `A`
- **Host / Name:** `h2s` (resolving `h2s.recovahq.com`)
- **TTL:** Auto / 300s

Verify DNS propagation before requesting SSL:
```bash
dig +short h2s.recovahq.com A
```

---

## 2. Clone into a Dedicated Directory on the VPS

SSH into `recova-1` and clone into `/var/www/recova-h2s` (do **not** place inside `/var/www/recova/production`):

```bash
sudo mkdir -p /var/www/recova-h2s
sudo chown -R "$USER":"$USER" /var/www/recova-h2s
git clone https://github.com/RecovaIT/Recova-H2S.git /var/www/recova-h2s
cd /var/www/recova-h2s
```

Verify none of the default H2S loopback ports are in use by the existing stack:
```bash
ss -ltn | grep -E ':3810|:8810' || echo "Ports 3810 and 8810 are free"
```
If either port is taken, set `H2S_FRONTEND_PORT` / `H2S_BACKEND_PORT` in `.env.vps` (created in step 3).

---

## 3. Launch Containers & Configure Nginx + SSL

### Option A — Automated Setup Script

1. Start containers, generate `.env.vps` secrets (`SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`), configure `/etc/nginx/sites-available/h2s.recovahq.com`, and reload Nginx:
   ```bash
   bash deploy/vps/setup-vps.sh --domain h2s.recovahq.com
   ```
2. Once `dig +short h2s.recovahq.com A` returns your VPS IP, issue Let's Encrypt SSL (or combine `--ssl` directly with step 1):
   ```bash
   sudo certbot --nginx -d h2s.recovahq.com --redirect
   ```

### Option B — Manual Step-by-Step

1. Copy `.env.vps` template and fill secrets:
   ```bash
   cp deploy/vps/.env.vps.example .env.vps
   chmod 600 .env.vps
   python3 -c 'import secrets; print("POSTGRES_PASSWORD=" + secrets.token_urlsafe(24)); print("SECRET_KEY=" + secrets.token_urlsafe(48))'
   python3 -c 'import base64, os; print("FIELD_ENCRYPTION_KEY=" + base64.urlsafe_b64encode(os.urandom(32)).decode())'
   nano .env.vps
   ```
2. Build and start the isolated Compose stack:
   ```bash
   docker compose -f docker-compose.vps.yml --env-file .env.vps up -d --build
   docker compose -f docker-compose.vps.yml --env-file .env.vps ps
   ```
3. Install the standalone Nginx virtual host (`recova` site config remains untouched):
   ```bash
   sed \
     -e 's|__H2S_DOMAIN__|h2s.recovahq.com|g' \
     -e 's|__H2S_BACKEND_PORT__|8810|g' \
     -e 's|__H2S_FRONTEND_PORT__|3810|g' \
     deploy/vps/nginx/h2s.recovahq.com.conf | sudo tee /etc/nginx/sites-available/h2s.recovahq.com >/dev/null

   sudo ln -sf /etc/nginx/sites-available/h2s.recovahq.com /etc/nginx/sites-enabled/h2s.recovahq.com
   sudo nginx -t && sudo systemctl reload nginx
   ```
4. Issue SSL with Certbot:
   ```bash
   sudo certbot --nginx -d h2s.recovahq.com --redirect
   ```

---

## 4. Verification & Post-Deploy Smoke Checks

```bash
# Container health
docker compose -f docker-compose.vps.yml --env-file .env.vps ps

# Backend DB readiness via HTTPS
curl -fsS https://h2s.recovahq.com/readyz
# Expected: {"status":"ready","database":"connected"}

# Auth bootstrap status via HTTPS
curl -fsS https://h2s.recovahq.com/api/v1/auth/status
# Expected: {"needs_bootstrap":true}  (until initial platform/organisation setup)
```

Before initializing production, set a private random `BOOTSTRAP_SETUP_TOKEN` of at least 32 characters in `.env.vps` and recreate the backend. Generate it with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep it private. The setup script generates it for a new environment file; existing files need this setting added manually. Enter it on `/bootstrap` when creating the intended platform operator. Clear the token and restart the backend after successful initialization. Public organization registration stays blocked until this step finishes.

Synthetic judge fixtures bypass real invitation delivery and are not proof of onboarding or production readiness. Only optionally load them in an explicitly designated demonstration environment:
```bash
# Optional: seed judge demo data (only on a fresh demo environment)
docker compose -f docker-compose.vps.yml --env-file .env.vps exec backend python scripts/seed_judge_demo.py
```

---

## 5. Routine Updates & Database Backups

### Pulling Updates (Zero Impact on Existing Stack)
```bash
cd /var/www/recova-h2s
git pull origin main
bash deploy/vps/setup-vps.sh
```
*(Because `nginx` config and `.env.vps` already exist, re-running `setup-vps.sh` preserves secrets and Certbot SSL rules while rebuilding containers and running `alembic upgrade head` automatically.)*

### PostgreSQL Backup (`recova_h2s`)
```bash
docker compose -f /var/www/recova-h2s/docker-compose.vps.yml --env-file /var/www/recova-h2s/.env.vps \
  exec -T postgres pg_dump -U recova_h2s recova_h2s > /var/www/recova-h2s/recova_h2s_backup.sql
```
