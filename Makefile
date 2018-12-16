# Some simple testing tasks (sorry, UNIX only).


flake:
	flake8 aiorwlock tests examples setup.py

test: flake
	pytest -s

vtest:
	pytest -v

checkrst:
	python setup.py check --restructuredtext

pyroma:
	pyroma -d .

bandit:
	bandit -r ./aiorwlock

mypy:
	mypy aiorwlock --ignore-missing-imports --disallow-untyped-calls --no-site-packages --strict

cov cover coverage: flake checkrst pyroma bandit
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
