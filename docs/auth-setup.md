# Auth and Datastore Setup

## Google OAuth (official rules)

Google’s **[Using OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)** doc states:

1. **Redirect URIs** — Endpoints where Google may send the authorization response. They must follow Google’s [validation rules](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation). For local testing you may use URIs that refer to the machine you’re developing on (the doc examples use ports like `http://localhost:8080`; **your port and path must match what your app sends**).

2. **Exact match** — The `redirect_uri` in the authorization request must **exactly** match one of the **Authorized redirect URIs** for that OAuth client. Per Google’s parameter table: *“The value must exactly match one of the authorized redirect URIs… **http** or **https** scheme, **case**, and **trailing slash** must all match.”* If it does not, you get **`redirect_uri_mismatch`**.

3. **`redirect_uri_mismatch`** — Google’s doc says: *“Review authorized redirect URIs in the Google Cloud Console [Clients page](https://console.developers.google.com/auth/clients).”*

**Authorized JavaScript origins** (no path) and **Authorized redirect URIs** (full URL including path) are separate fields in the OAuth client. Origins are typically `scheme + host + port` only.

### This app (Research Workflow UI)

- The backend route is **`GET /auth/callback`** (named `auth_callback`).
- With **Vite dev** (`npm run dev`), the browser uses the **frontend** origin (default **`http://localhost:48722`**). The app sends Google a redirect URI of **`{FRONTEND_URL}/auth/callback`** (see `backend/routers/auth.py`). So for local dev, register:

  - **Authorized redirect URIs:**  
    `http://localhost:48722/auth/callback`  
    (optionally also `http://127.0.0.1:48722/auth/callback` if you use that host.)

  - **Authorized JavaScript origins:**  
    `http://localhost:48722`  
    (and optionally `http://127.0.0.1:48722`.)

    If you only list your production origin (`https://lnpiapp.med.umn.edu`) here, **local** “Sign in with Google” can still fail. Add **`http://localhost:48722`** while testing on your machine.

  - Remove or avoid listing **only** `https://lnpiapp.med.umn.edu` as a **redirect URI** without the app path — your callback is **`…/research-automation/auth/callback`** in production, not the site root.

**Verify what this server sends:** open **`http://localhost:48722/auth/debug/oauth-redirect`** and check **`redirect_uri`** and **`google_client_id`**. The redirect URI must be registered on **that exact** OAuth client (not a different Web client in the same project). If `redirect_uri` is already listed but Google still returns `redirect_uri_mismatch`, you are almost certainly editing the wrong client or the backend is using another `.env` / old process — restart the backend and compare **`google_client_id`** to the Client ID at the top of the credential you edited.

**Shell exports vs `.env`:** If you ever ran `export GOOGLE_CLIENT_ID=...` (or set it in `~/.zshrc`), older setups could ignore your `.env` file for that variable. This project loads the project-root `.env` with **`override=True`** so **`.env` wins** after a backend restart. If **`warnings`** on the debug endpoint mention a mismatch with the file on disk, run `unset GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET FRONTEND_URL` in your terminal or fix the shell profile, then restart the backend.

- Do **not** assume the redirect URI is the raw API port (`:48721`) when you open the UI through Vite; the redirect URI must match what the backend **sends in the OAuth request** (aligned with `FRONTEND_URL`).

- Optional env override: **`OAUTH_REDIRECT_URI`** — full callback URL if you must pin it (e.g. unusual proxy setup).

Production: set **`FRONTEND_URL`** to your public UI base (e.g. `https://lnpiapp.med.umn.edu/research-automation`) and register **`https://lnpiapp.med.umn.edu/research-automation/auth/callback`** (exactly, per your reverse proxy) in Google Cloud.

## Google Cloud Console checklist

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable any APIs you need (e.g. **People API** for profile/email if required by your flow).
3. **APIs & Services → Credentials → Create OAuth client ID → Web application.**
4. Paste **Client ID** and **Client Secret** into `.env`:

   - `GOOGLE_CLIENT_ID=...`
   - `GOOGLE_CLIENT_SECRET=...`

5. Also set:

   - `SESSION_SECRET` — long random string for session cookies (e.g. `openssl rand -hex 32`).
   - `FRONTEND_URL` — browser URL for redirects after login/logout (e.g. `http://localhost:48722` in dev with this repo’s Vite default port).

## Datastore

### Development (default)

- `DATASTORE=memory` or leave unset.
- Sessions and users are stored in memory; no database required.
- Data is lost on backend restart.

### Production (MariaDB)

1. Create a MariaDB/MySQL database and user.
2. Set env:

   - `DATASTORE=mariadb`
   - `DATABASE_URL=mysql://user:password@host:3306/database_name`

3. On first run, the backend creates tables as needed.

Example:

```bash
export DATASTORE=mariadb
export DATABASE_URL=mysql://pipeline:secret@localhost:3306/pipeline_db
```

## Bypass login (development only)

Set backend env **`BYPASS_AUTH_DEV=1`**, run the frontend (`npm run dev`), then use **“Bypass login (development)”** on the login page. That hits `GET /auth/dev-login` (only when enabled) and creates a dev session (`dev@local`). **Do not enable in production.**

## Testing with Google OAuth

1. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` (and `FRONTEND_URL` for your dev URL).
2. Register the matching **`{FRONTEND_URL}/auth/callback`** in Google Cloud (see above).
3. Restart the backend, open the frontend (e.g. `http://localhost:48722/login`), and use **Sign in with Google**.

To debug **`redirect_uri_mismatch`**, compare the `redirect_uri` in the failing Google URL or error details with the **Authorized redirect URIs** list — they must be identical (scheme, host, port, path, trailing slash, and letter case).

### Still seeing an error (400) after Google?

1. **Error on Google’s page (`accounts.google.com`)** — Google rejected the *authorization* request. Fix redirect URIs / JavaScript origins (above). Wait a few minutes after saving in Google Cloud.

2. **Error after redirect back to your app (`…/auth/callback`)** — Our server shows an HTML error page with details.
   - **`error=redirect_uri_mismatch` in the URL** — Still a Console mismatch; use **`GET /auth/debug/oauth-redirect`** and compare exactly.
   - **Token / state errors** — Often **session cookie** loss: use **`http://localhost:48722`** consistently in the browser (**not** `http://127.0.0.1:48722`; cookies differ). Clear site data for localhost and try again. Restart backend after changing `.env`.

3. **OAuth consent screen in “Testing”** — Only **test users** you added in Google Cloud can sign in until the app is published.
