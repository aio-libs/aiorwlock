# Some simple testing tasks (sorry, UNIX only).

FILES := aiorwlock tests examples setup.py


flake:
	flake8 $(FILES)

fmt:
	isort ${FILES}
	black -S -l 79 ${FILES}

lint: bandit pyroma
	isort --check-only --diff ${FILES}
	black -S -l 79 --check $(FILES)
	mypy --show-error-codes --disallow-untyped-calls --strict aiorwlock
	flake8 $(FILES)

test: flake
	pytest -s

vtest:
	pytest -v

pyroma:
	pyroma -d .

bandit:
	bandit -r ./aiorwlock

mypy:
	mypy aiorwlock --disallow-untyped-calls --strict

cov cover coverage:
	pytest -sv --cov=aiorwlock --cov-report=term --cov-report=html ./tests
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
