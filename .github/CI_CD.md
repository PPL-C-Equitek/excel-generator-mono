# CI/CD Documentation

This repository uses 3 GitHub Actions workflows:

- `.github/workflows/backend.yml`
- `.github/workflows/frontend.yml`
- `.github/workflows/behavioral.yml`

`backend.yml` and `frontend.yml` implement CI (test, coverage, Sonar) and CD (deploy on push).
`behavioral.yml` adds Playwright behavioral smoke coverage for key user flows.

## 1) Workflow Triggers

### Backend (`backend.yml`)

- `push` to `main` when files change in:
  - `backend/**`
  - `scripts/deploy-backend.sh`
- `pull_request` targeting `main` when files change in:
  - `backend/**`
  - `scripts/deploy-backend.sh`
  - `.github/workflows/backend.yml`

### Frontend (`frontend.yml`)

- `push` to `main` when files change in:
  - `frontend/**`
  - `scripts/deploy-frontend.sh`
- `pull_request` targeting `main` when files change in:
  - `frontend/**`
  - `scripts/deploy-frontend.sh`
  - `.github/workflows/frontend.yml`

### Behavioral (`behavioral.yml`)

- `push` to `main` when files change in:
  - `frontend/**`
  - `backend/**`
  - `docker-compose.e2e.yml`
  - `.github/workflows/behavioral.yml`
- `pull_request` targeting `main` when files change in:
  - `frontend/**`
  - `backend/**`
  - `docker-compose.e2e.yml`
  - `.github/workflows/behavioral.yml`

## 2) CI Stages

Each workflow has 3 jobs: `test`, `sonar`, `deploy`.

### `test` job

- Backend:
  - setup Python
  - install dependencies
  - lint (`ruff`)
  - migration check
  - run tests with coverage
  - upload coverage artifacts
  - generate/update coverage badge SVG
- Frontend:
  - setup Node
  - install dependencies
  - lint
  - build
  - run tests with coverage
  - upload coverage artifacts
  - generate/update coverage badge SVG

### `sonar` job

- Runs after `test` (`needs: test`).
- Uses SonarCloud scan action.
- Waits for quality gate (`sonar.qualitygate.wait=true`).

## 3) CD Stage (`deploy` job)

- Runs only on `push` events (`if: github.event_name == 'push'`).
- Runs after successful `test` and `sonar` jobs.
- Connects to VM via SSH (`appleboy/ssh-action`).
- Writes runtime `.env` on server from GitHub `vars` and `secrets`.
- Pulls latest code on server and runs deploy script:
  - backend: `bash scripts/deploy-backend.sh`
  - frontend: `bash scripts/deploy-frontend.sh`

## 4) Behavioral Smoke Stage (`behavioral.yml`)

The behavioral workflow runs Playwright smoke tests against native app processes in CI:

- starts a PostgreSQL service container in GitHub Actions
- installs backend and frontend dependencies directly on the runner
- Playwright starts Django on `localhost:8000` and Next.js on `localhost:3000`
- global setup runs Django migrations and seeds deterministic e2e data
- smoke coverage currently includes:
  - login bootstrap
  - logout
  - protected-route redirect
  - history rename/delete
  - schema create/edit/delete

## 5) Coverage Badge Update Behavior

Coverage badge updates only run for:

- `push` events on `main`
- internal `pull_request` events targeting `main` (same repository, not fork PR)

For these events, the workflow resolves the target branch dynamically:

- PR: `GITHUB_HEAD_REF` (source branch of the PR within this repository)
- Push to `main`: `GITHUB_REF_NAME` (which is `main` with the current workflow config)

It then commits and pushes badge changes back to that branch.

Badge files:

- `.github/badges/backend-coverage.svg`
- `.github/badges/frontend-coverage.svg`

## 6) Required GitHub Configuration

### Secrets

- `SONAR_TOKEN`
- `GITHUB_TOKEN` (provided by Actions)
- `VM_HOST`
- `VM_USER`
- `VM_PASSWORD`
- `POSTGRES_PASSWORD`
- `DJANGO_SECRET_KEY`
- `JWT_SECRET_KEY`
- `OPENAI_API_KEY`
- `RESEND_API_KEY`

### Variables (`Repository Variables`)

- `SONAR_ORGANIZATION`
- `SONAR_PROJECT_KEY_BACKEND`
- `SONAR_PROJECT_KEY_FRONTEND`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `NEXT_PUBLIC_API_URL`
- `FRONTEND_URL`
- `GOOGLE_OAUTH_CLIENT_ID`
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
- `OPENAI_MODEL`
- `OPENAI_SYSTEM_PROMPT`
- `LLM_CACHE_TTL_SECONDS`
- `RESEND_FROM_EMAIL`
- `MEDIA_ROOT`
- `CSV_EXPORT_DIR`
- `EXCEL_EXPORT_DIR`
- `TESSERACT_LANG`

### Required Status Check

To make behavioral testing mandatory before merge, enable a branch protection rule or ruleset in GitHub and mark the workflow job `Behavioral Smoke` as a required status check for `main`.

This cannot be fully enforced from the repository files alone; it must be enabled in the repository settings.

## 7) Failure Rules

- If `test` fails: `sonar` and `deploy` do not run.
- If `sonar` quality gate fails: `deploy` does not run.
- If the badge update `git push` fails: the workflow retries the push command up to 3 times; failures in earlier git steps (`fetch`/`checkout`) fail immediately and are not retried.

## 8) How to Monitor

- CI/CD runs: GitHub tab `Actions`
- Workflow files:
  - `.github/workflows/backend.yml`
  - `.github/workflows/frontend.yml`
  - `.github/workflows/behavioral.yml`

## 9) TLS / HTTPS Setup

The application is served over HTTPS using **Nginx** as a reverse proxy and **Let's Encrypt** (via Certbot) for TLS certificates.

### Domains

| Domain | Proxies to | Nginx config file |
|---|---|---|
| `excelproject.equitek.id` | `127.0.0.1:3000` (Next.js frontend) | `/etc/nginx/sites-enabled/excelproject` |
| `excelproject-api.equitek.id` | `127.0.0.1:8000` (Django backend) | `/etc/nginx/sites-enabled/excelproject-api` |

Both domains also cover their `www.` variants. HTTP (port 80) requests are automatically redirected to HTTPS (port 443) by Certbot-managed server blocks.

### Certificate Details

Certificates are issued by Let's Encrypt using ECDSA keys and stored at:

- `/etc/letsencrypt/live/excelproject.equitek.id/fullchain.pem`
- `/etc/letsencrypt/live/excelproject-api.equitek.id/fullchain.pem`

Shared TLS settings are in `/etc/letsencrypt/options-ssl-nginx.conf` and DH params in `/etc/letsencrypt/ssl-dhparams.pem` (both managed by Certbot).

### Auto-Renewal

Certbot runs twice daily via systemd timer (`certbot.timer`). Certificates are renewed automatically when fewer than 30 days remain before expiry. Nginx is reloaded automatically after successful renewal.

Verify renewal is working:

```bash
sudo certbot renew --dry-run
```

Check timer status:

```bash
sudo systemctl status certbot.timer
```

### Firewall

UFW is currently **inactive** on the server. If enabled in the future, ensure ports 80 and 443 are allowed:

```bash
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### Initial Setup (for new server or domain)

1. Install Nginx and Certbot:

   ```bash
   sudo apt update
   sudo apt install nginx certbot python3-certbot-nginx
   ```

2. Create an Nginx site config in `/etc/nginx/sites-available/yoursite`:

   **Frontend example:**

   ```nginx
   server {
       listen 80;
       server_name yourdomain.equitek.id www.yourdomain.equitek.id;

       location / {
           proxy_pass http://127.0.0.1:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
       }
   }
   ```

   **Backend example:**

   ```nginx
   server {
       listen 80;
       server_name yourdomain-api.equitek.id www.yourdomain-api.equitek.id;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. Enable the site and test:

   ```bash
   sudo ln -s /etc/nginx/sites-available/yoursite /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

4. Run Certbot to obtain certificates and auto-configure SSL (this modifies the config above to add the `listen 443 ssl` block and HTTP→HTTPS redirect):

   ```bash
   sudo certbot --nginx -d yourdomain.equitek.id -d www.yourdomain.equitek.id
   ```

5. Verify the certbot timer is active:

   ```bash
   sudo systemctl enable certbot.timer
   sudo systemctl start certbot.timer
   ```

### Troubleshooting

- **Check certificate expiry:** `sudo certbot certificates`
- **Test Nginx config:** `sudo nginx -t`
- **Reload Nginx after manual config changes:** `sudo systemctl reload nginx`
- **Check Nginx error logs:** `sudo tail -f /var/log/nginx/error.log`
- **Force renewal (if needed):** `sudo certbot renew --force-renewal`
