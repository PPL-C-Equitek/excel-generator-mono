# CI/CD Documentation

This repository uses 2 GitHub Actions workflows:

- `.github/workflows/backend.yml`
- `.github/workflows/frontend.yml`

Both workflows implement CI (test, coverage, Sonar) and CD (deploy on push).

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

## 4) Coverage Badge Update Behavior

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

## 5) Required GitHub Configuration

### Secrets

- `SONAR_TOKEN`
- `GITHUB_TOKEN` (provided by Actions)
- `VM_HOST`
- `VM_USER`
- `VM_PASSWORD`
- `POSTGRES_PASSWORD`
- `DJANGO_SECRET_KEY`
- `OPENAI_API_KEY`

### Variables (`Repository Variables`)

- `SONAR_ORGANIZATION`
- `SONAR_PROJECT_KEY_BACKEND`
- `SONAR_PROJECT_KEY_FRONTEND`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `NEXT_PUBLIC_API_URL`
- `OPENAI_MODEL`
- `OPENAI_SYSTEM_PROMPT`

## 6) Failure Rules

- If `test` fails: `sonar` and `deploy` do not run.
- If `sonar` quality gate fails: `deploy` does not run.
- If the badge update `git push` fails: the workflow retries the push command up to 3 times; failures in earlier git steps (`fetch`/`checkout`) fail immediately and are not retried.

## 7) How to Monitor

- CI/CD runs: GitHub tab `Actions`
- Workflow files:
  - `.github/workflows/backend.yml`
  - `.github/workflows/frontend.yml`
