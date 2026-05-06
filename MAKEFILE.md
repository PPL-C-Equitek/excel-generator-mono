# Makefile Documentation

The root [`Makefile`](./Makefile) provides shortcuts for common backend, frontend, Docker, and deployment tasks. Run all commands from the repository root.

## Quick Start

Show all available commands:

```bash
make help
```

## Prerequisites

- GNU Make
- Backend prerequisites from [`README.md`](./README.md#system-prerequisites)
- Frontend dependencies (`Node.js` and `npm`)
- Docker Compose for Docker commands
- Deployment tools only when running deployment targets (`venv`, `systemd`, `nvm`, and `pm2` on the target server)

## General Targets

| Command | Description |
| --- | --- |
| `make help` | Print all available Makefile targets. |
| `make deploy` | Run backend and frontend deployment targets sequentially. |
| `make deploy-backend` | Run `scripts/deploy-backend.sh` for Django/Gunicorn deployment. |
| `make deploy-frontend` | Run `scripts/deploy-frontend.sh` for Next.js/PM2 deployment. |

## Backend Targets

| Command | Description |
| --- | --- |
| `make backend-install` | Install backend dependencies from `backend/requirements.txt`. |
| `make backend-migrate` | Run Django database migrations. |
| `make backend-seed` | Seed member data with `python manage.py seed_members`. |
| `make backend-run` | Start the Django development server. |
| `make backend-test` | Run the Django test suite. |
| `make backend-test-coverage` | Run backend tests with coverage report and XML output. |

## Frontend Targets

| Command | Description |
| --- | --- |
| `make frontend-install` | Install frontend dependencies with `npm ci`. |
| `make frontend-build` | Build the Next.js frontend. |
| `make frontend-run` | Start the frontend production server. |
| `make frontend-dev` | Start the frontend development server. |
| `make frontend-lint` | Run frontend lint checks. |
| `make frontend-test` | Run frontend tests. |
| `make frontend-test-coverage` | Run frontend tests with coverage. |

## Docker Targets

| Command | Description |
| --- | --- |
| `make docker-up` | Start `docker-compose.dev.yml` in detached mode. |
| `make docker-down` | Stop and remove services from `docker-compose.dev.yml`. |

## Common Workflows

Start the local Docker stack:

```bash
make docker-up
```

Run the backend locally:

```bash
make backend-install
make backend-migrate
make backend-run
```

Run the frontend locally:

```bash
make frontend-install
make frontend-dev
```

Run tests:

```bash
make backend-test
make frontend-test
```

## Deployment Notes

### Backend Deployment

`make deploy-backend` expects:

- App directory at `~/apps/excel-generator-mono/backend`
- Python virtual environment at `backend/venv`
- Environment values in `~/apps/.env`
- A `gunicorn` systemd service

The target runs `scripts/deploy-backend.sh`, which installs backend dependencies, runs migrations, seeds member data, collects static files, and restarts Gunicorn.

### Frontend Deployment

`make deploy-frontend` expects:

- App directory at `~/apps/excel-generator-mono/frontend`
- `nvm` installed at `~/.nvm`
- Environment values in `~/apps/.env`
- PM2 available to manage the `nextjs` process

The target runs `scripts/deploy-frontend.sh`, which installs frontend dependencies, builds the Next.js app, and restarts or starts the PM2 `nextjs` process.
