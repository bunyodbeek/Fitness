#!/bin/bash
# Butun skript { ... } ichida: bash uni avval to'liq o'qib oladi. `git pull` shu
# faylning o'zini yangilasa ham, ishlab turgan nusxa yarmidan buzilib qolmaydi.
{
set -euo pipefail

cd /var/www/fitness
# --ff-only: serverda qo'lda qilingan o'zgarish bo'lsa, ustidan yozmasdan to'xtaydi.
git pull --ff-only origin main

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

pip install -q -r req.txt

python manage.py migrate --noinput
# REDIS_URL o'rnatilmagan bo'lsa, cache DatabaseCache'ga tushadi va u jadval talab
# qiladi (OTP/to'lov guard'lari shunga bog'liq). Idempotent — mavjud bo'lsa e'tibor
# bermaydi. Redis ishlatilsa ham zararsiz.
python manage.py createcachetable
# Tarjimalar .mo fayllardan o'qiladi. .mo repoda saqlanadi, lekin .po yangilanib
# .mo eskirib qolgan holatdan himoya qilish uchun qayta kompilyatsiya qilamiz.
python manage.py compilemessages --ignore=venv --ignore=.venv
python manage.py collectstatic --noinput

# deploy foydalanuvchisiga faqat shu buyruq parolsiz ruxsat etilgan
# (/etc/sudoers.d/91-deploy-gunicorn).
sudo -n systemctl restart gunicorn
echo "Deploy OK: $(git log --oneline -1)"
exit
}
