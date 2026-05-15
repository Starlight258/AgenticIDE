.PHONY: install dev test lint format check clean help

help:
	@echo "make install   — sync deps from uv.lock"
	@echo "make dev       — start FastAPI dev server (auto-reload)"
	@echo "make test      — run pytest"
	@echo "make lint      — ruff check"
	@echo "make format    — ruff format (autofix)"
	@echo "make check     — ruff check + format-check (no fix, CI-style)"
	@echo "make clean     — remove cache dirs"

install:
	uv sync

dev:
	uv run fastapi dev src/main.py

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check .
	uv run ruff format --check .

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ *.egg-info
