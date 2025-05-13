build:
	docker compose -f local.yml up --build -d --remove-orphans

up:
	docker compose -f local.yml up -d

down:
	docker compose -f local.yml down

down-v:
	docker compose -f local.yml down -v

pybank-config:
	docker compose -f local.yml config

makemigrations:
	docker compose -f local.yml run --rm api python manage.py makemigrations

migrate:
	docker compose -f local.yml run --rm api python manage.py migrate

collectstatic:
	docker compose -f local.yml run --rm api python manage.py collectstatic --no-input

superuser:
	docker compose -f local.yml run --rm api python manage.py createsuperuser

flush:
	docker compose -f local.yml run --rm api python manage.py flush

network-inspect:
	docker network inspect pybank_local_nw

pybank-db:
	docker compose -f local.yml exec postgres psql --username=postgres --dbname=banker
