SHELL := /bin/bash

# Paths
ROOT_DIR := $(CURDIR)
BACKEND_DIR := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend
SCRIPTS_DIR := $(ROOT_DIR)/scripts

.PHONY: help deploy deploy-backend deploy-frontend init-db \
	backend-install backend-migrate backend-seed backend-run backend-test backend-test-coverage \
	frontend-install frontend-build frontend-run frontend-dev frontend-test frontend-test-coverage \
	docker-up docker-down

help:
	@echo "Available targets:"
	@echo "  make deploy                 - Deploy backend + frontend"
	@echo "  make deploy-backend         - Deploy backend (Django/Gunicorn)"
	@echo "  make deploy-frontend        - Deploy frontend (Next.js/PM2)"
	@echo ""
	@echo "Backend targets:"
	@echo "  make backend-install        - Install backend requirements"
	@echo "  make backend-migrate        - Run Django migrations"
	@echo "  make backend-seed           - Seed member data"
	@echo "  make backend-run            - Start Django dev server"
	@echo "  make backend-test           - Run backend tests"
	@echo "  make backend-test-coverage  - Run backend tests with coverage"
	@echo ""
	@echo "Frontend targets:"
	@echo "  make frontend-install       - Install frontend dependencies"
	@echo "  make frontend-build         - Build frontend"
	@echo "  make frontend-run           - Start frontend production server"
	@echo "  make frontend-dev           - Start frontend dev server"
	@echo "  make frontend-test          - Run frontend tests"
	@echo "  make frontend-test-coverage - Run frontend tests with coverage"
	@echo ""
	@echo "Docker targets:"
	@echo "  make docker-up              - Start docker-compose.dev.yml"
	@echo "  make docker-down            - Stop docker-compose.dev.yml"

deploy: deploy-backend deploy-frontend

deploy-backend:
	@bash "$(SCRIPTS_DIR)/deploy-backend.sh"

deploy-frontend:
	@bash "$(SCRIPTS_DIR)/deploy-frontend.sh"

backend-install:
	@cd "$(BACKEND_DIR)" && pip install -r requirements.txt

backend-migrate:
	@cd "$(BACKEND_DIR)" && python manage.py migrate

backend-seed:
	@cd "$(BACKEND_DIR)" && python manage.py seed_members

backend-run:
	@cd "$(BACKEND_DIR)" && python manage.py runserver

backend-test:
	@cd "$(BACKEND_DIR)" && python manage.py test

backend-test-coverage:
	@cd "$(BACKEND_DIR)" && coverage run --rcfile=.coveragerc manage.py test && coverage report && coverage xml

frontend-install:
	@cd "$(FRONTEND_DIR)" && npm ci

frontend-build:
	@cd "$(FRONTEND_DIR)" && npm run build

frontend-run:
	@cd "$(FRONTEND_DIR)" && npm run start

frontend-dev:
	@cd "$(FRONTEND_DIR)" && npm run dev

frontend-test:
	@cd "$(FRONTEND_DIR)" && npm run test

frontend-test-coverage:
	@cd "$(FRONTEND_DIR)" && npm run test:coverage

docker-up:
	@docker compose -f "$(ROOT_DIR)/docker-compose.dev.yml" up -d

docker-down:
	@docker compose -f "$(ROOT_DIR)/docker-compose.dev.yml" down
