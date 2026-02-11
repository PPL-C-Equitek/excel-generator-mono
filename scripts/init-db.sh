#!/bin/bash
set -e

cd backend
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

python manage.py migrate
python manage.py seed_members

if [ -n "${VIRTUAL_ENV:-}" ]; then
  deactivate
fi
