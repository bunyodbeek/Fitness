#!/bin/bash
set -e

cd /var/www/fitness
git pull origin main

# Virtual muhit papkasi serverda `venv`, lokalda `.venv` deb nomlangan. Ilgari bu
# yerda qat'iy `.venv` yozilgan edi — serverda bunday papka yo'q, `source` xato
# qaytaradi va `set -e` tufayli skript SHU YERDA to'xtaydi. Natijada `git pull`
# ishlaydi-yu, `migrate` ishlamaydi: yangi kod eski sxema bilan ishga tushib,
# "column ... does not exist" xatosini beradi. Endi mavjud papkani topamiz.
VENV=""
for candidate in venv .venv env; do
    if [ -f "$candidate/bin/activate" ]; then
        VENV="$candidate"
        break
    fi
done
if [ -z "$VENV" ]; then
    echo "ERROR: virtualenv topilmadi (venv/.venv/env tekshirildi)." >&2
    exit 1
fi
echo "Using virtualenv: $VENV"
source "$VENV/bin/activate"

pip install -r req.txt

python manage.py migrate --noinput
# REDIS_URL o'rnatilmagan bo'lsa, cache DatabaseCache'ga tushadi va u jadval talab
# qiladi (OTP/to'lov guard'lari shunga bog'liq). Idempotent — mavjud bo'lsa e'tibor
# bermaydi. Redis ishlatilsa ham zararsiz.
python manage.py createcachetable
# Tarjimalar .mo fayllardan o'qiladi. .mo repoda saqlanadi, lekin .po yangilanib
# .mo eskirib qolgan holatdan himoya qilish uchun qayta kompilyatsiya qilamiz.
python manage.py compilemessages --ignore=venv --ignore=.venv
python manage.py collectstatic --noinput

systemctl restart gunicorn
