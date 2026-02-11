#!/bin/bash
set -e

set -a
source ~/apps/.env
set +a

cd ~/apps/excel-generator-mono/backend

source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_members
python manage.py collectstatic --noinput
deactivate

sudo systemctl restart gunicorn
