#!/bin/bash
set -e

cd /var/www/fitness
git pull origin main

source .venv/bin/activate
pip install -r req.txt

python manage.py migrate --noinput
# REDIS_URL o'rnatilmagan bo'lsa, cache DatabaseCache'ga tushadi va u jadval talab
# qiladi (OTP/to'lov guard'lari shunga bog'liq). Idempotent — mavjud bo'lsa e'tibor
# bermaydi. Redis ishlatilsa ham zararsiz.
python manage.py createcachetable
python manage.py collectstatic --noinput

systemctl restart gunicorn
