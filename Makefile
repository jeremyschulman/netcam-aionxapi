.PHONY: setup.py requirements.txt

DIST_BASENAME := $(shell poetry version | tr ' ' '-')

all: precheck

.PHONY: prechck
precheck:
	invoke precheck


clean:
	rm -rf dist *.egg-info .pytest_cache
	rm -f poetry.lock
	find . -name '__pycache__' | xargs rm -rf
