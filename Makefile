.PHONY: install
install:
	poetry install

.PHONY: migrations
migrations:
	poetry run python3 -m backend.manage makemigrations

.PHONY: migrate
migrate:
	poetry run python3 -m backend.manage migrate

.PHONY: run-server
run-server:
	poetry run python3 -m backend.manage runserver

.PHONY: shell
shell:
	poetry run python -m backend.manage shell

.PHONY: superuser
superuser:
	poetry run python3 -m backend.manage createsuperuser

.PHONY: update
update: install migrate ;

.PHONY: local-settings
local-settings:
	mkdir -p local
	cp ./backend/UnTube/settings/templates/settings.dev.py ./local/settings.dev.py