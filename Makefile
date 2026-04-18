mig:
	python3 manage.py makemigrations
	python3 manage.py migrate

user:
	python3 manage.py createsuperuser

loaddata:
	python3 manage.py loaddata program edition exercises workout workoutexercise

check:
	isort .
	flake8 .

ngrok:
	ngrok http 8000


lang:
	django-admin makemessages -l uz -l en -l ru

compile:
	django-admin compilemessages -i .venv

setup:
	python3 setup_webhook.py