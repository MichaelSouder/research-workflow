# Deploying on lnpiapp.med.umn.edu (or similar)

This app runs as three containers: **MariaDB**, **FastAPI backend**, and **nginx + static frontend**. The frontend nginx proxies `/api` and `/auth` to the backend on the Docker network. You normally expose only the frontend port to users (or bind it to loopback and put the university reverse proxy in front).

## One-time server setup

1. **Install Docker and Docker Compose v2** (plugin or standalone) if not already present.
2. **Create a project directory**, e.g. `~/qualtrics-automation`.
3. **Copy environment file** from the repo (on the server or after first clone):

   ```bash
   cp .env.production.example .env.production
   ```

   Edit `.env.production` and set at least:

   - `FRONTEND_URL=https://lnpiapp.med.umn.edu` (or the exact URL users will use)
   - `CORS_ORIGINS` — same origin as `FRONTEND_URL`
   - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — OAuth client for a **Web application**
   - `SESSION_SECRET` — long random secret (e.g. `openssl rand -hex 32`)
   - `BACKEND_PUBLISH=127.0.0.1:48721:48721` — keeps the API off the public interface; the UI still talks to the backend inside Compose

4. **Google Cloud Console** — add an authorized redirect URI:

   `https://lnpiapp.med.umn.edu/auth/callback`

   (Match the scheme and host to `FRONTEND_URL`.)

5. **Host reverse proxy / TLS** — if the VM already runs Apache or nginx with TLS, point it at the app:

   - Upstream: `http://127.0.0.1:48722` (default published port for the frontend container)
   - Or set `FRONTEND_PUBLISH=127.0.0.1:48722:80` in `.env.production` so only the loopback can reach the UI container; then proxy `https://lnpiapp.med.umn.edu` → `http://127.0.0.1:48722`.

6. **Firewall** — allow only 22 (SSH) and 443 (HTTPS) from the internet if the reverse proxy terminates TLS; do not expose MariaDB or the backend port publicly.

## Deploy from your laptop (build on the server)

Requires SSH access and `rsync`.

```bash
export DEPLOY_SSH='your_netid@lnpiapp.med.umn.edu'
export DEPLOY_REMOTE_DIR='~/qualtrics-automation'
./deploy/sync-and-up.sh
```

The first time, create `.env.production` on the server before running the script (the script does not upload `.env` from your machine).

## Deploy with a container registry (build locally, pull on server)

Use when the server should not compile images.

```bash
export REGISTRY='your-registry.example.edu/research-workflow'
export DEPLOY_SSH='your_netid@lnpiapp.med.umn.edu'
export DEPLOY_REMOTE_DIR='~/qualtrics-automation'
docker login "$REGISTRY"   # if required
./deploy/push-images.sh
```

Ensure `.env.production` exists on the server. The script copies only `docker-compose.yml` and `docker-compose.prod.yml` and runs `compose pull` + `up` with the same image tags.

## Manual run on the server

```bash
cd ~/qualtrics-automation
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=100
```

## Data persistence

- **MariaDB** data is in the named volume `mariadb_data` (see `docker compose` volume list).
- **Custom pipeline components** are bind-mounted from `backend/custom_components` on the host; keep that directory on the server across deploys.
- **Workspace** files use `backend/workspace` similarly.

## What I cannot do from here

Automated pushes to `lnpiapp.med.umn.edu` require **your** SSH identity, VPN, and any **UMN IT approvals**. Run the scripts from a machine that already has access; if you use a shared registry, coordinate credentials with your team.
