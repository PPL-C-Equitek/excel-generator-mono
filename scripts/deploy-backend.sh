#!/bin/bash
set -e

source "$(dirname "$0")/load-env.sh"
load_env_file "$HOME/apps/.env"

cd ~/apps/excel-generator-mono/backend

source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_members
python manage.py collectstatic --noinput
deactivate

sudo systemctl restart gunicorn
