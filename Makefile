# Some simple testing tasks (sorry, UNIX only).

FILES := aiorwlock tests examples


flake:
	poetry run ruff check $(FILES)

fmt:
	poetry run ruff check --fix $(FILES)
	poetry run ruff format $(FILES)

lint: bandit pyroma
	poetry run ruff check $(FILES)
	poetry run ruff format --check --diff $(FILES)
	poetry run mypy --show-error-codes --disallow-untyped-calls --strict aiorwlock

test: flake
	poetry run pytest -s

vtest:
	poetry run pytest -v

pyroma:
	poetry run pyroma -d .

bandit:
	poetry run bandit -r ./aiorwlock

mypy:
	poetry run mypy aiorwlock --disallow-untyped-calls --strict

cov cover coverage:
	poetry run pytest -sv --cov=aiorwlock --cov-report=term --cov-report=html ./tests
	@echo "open file://`pwd`/htmlcov/index.html"

clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -f `find . -type f -name '@*' `
	rm -f `find . -type f -name '#*#' `
	rm -f `find . -type f -name '*.orig' `
	rm -f `find . -type f -name '*.rej' `
	rm -f .coverage
	rm -rf coverage
	rm -rf build
	rm -rf cover
	rm -rf dist

doc:
	make -C docs html
	@echo "open file://`pwd`/docs/_build/html/index.html"

.PHONY: all flake test vtest cov clean doc
