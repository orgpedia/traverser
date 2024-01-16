.DEFAULT_GOAL := help



tasks :=  # IMP: Write al the tasks here
tasks := $(foreach t,$(tasks),flow/$t)


.PHONY: help install import flow export check readme lint format pre-commit $(tasks)

help:
	$(info Please use 'make <target>', where <target> is one of)
	$(info )
	$(info   install     install packages and prepare software environment)
	$(info )
	$(info   lint        run the code linters)
	$(info   format      reformat code)
	$(info   pre-commit  run pre-commit checks, runs yaml lint, you need pre-commit)
	$(info )
	$(info Check the makefile to know exactly what each target is doing.)
	@echo # dummy command

install: pyproject.toml
	poetry install --only=dev

lint:
	poetry run black -q .
	poetry run ruff .

format:
	poetry run black -q .
	poetry run ruff --fix .

