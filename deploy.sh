#!/bin/bash
set -e

cd /var/www/fitness
git pull origin main

source .venv/bin/activate
pip install -r req.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput

systemctl restart gunicorn
