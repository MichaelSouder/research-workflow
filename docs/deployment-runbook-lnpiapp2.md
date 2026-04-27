# Deployment Runbook (`lnpiapp2.med.umn.edu`)

This is a short, copy/paste deployment checklist for this app.

## Target setup

- SSH host: `lnpiapp.med.umn.edu`
- SSH user: `soude017`
- Public URL: `https://lnpiapp2.med.umn.edu`
- App stack: Docker Compose (`backend`, `frontend`) + external MariaDB
- Reverse proxy/TLS: handled separately by host proxy

## 1) Connect and update code

```bash
ssh soude017@lnpiapp.med.umn.edu
cd ~/qualtrics-automation   # or your actual deploy path
git pull
```

## 2) Configure production environment

```bash
cp .env.production.example .env.production
```

Set these values in `.env.production`:

- `FRONTEND_URL=https://lnpiapp2.med.umn.edu`
- `CORS_ORIGINS=https://lnpiapp2.med.umn.edu`
- `GOOGLE_CLIENT_ID=<oauth-web-client-id>`
- `GOOGLE_CLIENT_SECRET=<oauth-web-client-secret>`
- `SESSION_SECRET=<long-random-secret>`
- `HTTPS=1`
- `BACKEND_PUBLISH=127.0.0.1:48721:48721`
- `FRONTEND_PUBLISH=127.0.0.1:48722:80`
- `DATASTORE=mariadb`
- `DATABASE_URL=mysql://<db_user>:<db_password>@<db_host>:3306/<db_name>`

Generate a session secret if needed:

```bash
openssl rand -hex 32
```

## 3) Production database (external MariaDB)

When using a production DB outside Docker:

1. **Do not use the Compose `db` service** for runtime. In `docker-compose.yml`, `db` is behind the **`local-db` profile** and is **not** started unless you pass `--profile local-db`.
2. Ensure the DB user has permissions on your production schema (`SELECT/INSERT/UPDATE/DELETE/CREATE/ALTER`).
3. Ensure network access from app host to DB host on `3306` (or your DB port).
4. Set `DATABASE_URL` in `.env.production` with URL-encoded password if it contains special characters.

Example:

```env
DATASTORE=mariadb
DATABASE_URL=mysql://app_user:strong%40password@prod-db-host.med.umn.edu:3306/pipeline_db
```

Quick connectivity test from app host:

```bash
python - <<'PY'
import pymysql
conn = pymysql.connect(
    host="prod-db-host.med.umn.edu",
    user="app_user",
    password="strong@password",
    database="pipeline_db",
    port=3306,
    connect_timeout=5,
)
print("db connection ok")
conn.close()
PY
```

## 4) Build and run containers (without local db)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --build backend frontend
```

**Local dev with the bundled MariaDB** (optional):

```bash
docker compose --profile local-db up -d db
# then start backend (same terminal / same project directory):
docker compose up -d backend frontend
```

If you previously ran the local db container, remove it from this stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production stop db
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production rm -f db
```

## 5) Verify locally on the server

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production ps
curl -I http://127.0.0.1:48722/
curl -I http://127.0.0.1:48721/auth/dev-bypass-status
```

Logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs -f backend frontend
```

Optional DB verification in logs (first startup):

- backend logs should **not** show DB auth/connection errors
- backend should finish startup and serve requests

## 6) Reverse proxy target

Point host proxy for `https://lnpiapp2.med.umn.edu` to:

- `http://127.0.0.1:48722`

The frontend container already proxies `/api` and `/auth` to backend internally.

### Reverse proxy checklist (what you must configure)

1. TLS certificate for `lnpiapp2.med.umn.edu`.
2. Proxy upstream to `127.0.0.1:48722`.
3. Forward standard proxy headers:
   - `Host`
   - `X-Forwarded-For`
   - `X-Forwarded-Proto`
4. Allow websocket upgrade headers (safe default).
5. Keep client body size/timeouts high enough for your workflows.

### Nginx example

```nginx
server {
    listen 443 ssl http2;
    server_name lnpiapp2.med.umn.edu;

    # ssl_certificate /path/fullchain.pem;
    # ssl_certificate_key /path/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:48722;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Apache example (if needed)

```apache
<VirtualHost *:443>
    ServerName lnpiapp2.med.umn.edu

    # SSLEngine on
    # SSLCertificateFile ...
    # SSLCertificateKeyFile ...

    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    ProxyPass / http://127.0.0.1:48722/
    ProxyPassReverse / http://127.0.0.1:48722/
</VirtualHost>
```

## 7) Google OAuth settings

In Google Cloud Console (same OAuth web client as `GOOGLE_CLIENT_ID`):

- Authorized JavaScript origins:
  - `https://lnpiapp2.med.umn.edu`
- Authorized redirect URIs:
  - `https://lnpiapp2.med.umn.edu/auth/callback`

These must match exactly (`scheme`, host, path).

## 8) Common update cycle

```bash
ssh soude017@lnpiapp.med.umn.edu
cd ~/qualtrics-automation
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --build backend frontend
```

