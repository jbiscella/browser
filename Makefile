.PHONY: setup test smoke handshake licenses clean

VENV := .venv/bin

setup:
	python3 -m venv .venv
	$(VENV)/python -m pip install -q --upgrade pip
	$(VENV)/pip install -e ".[dev]"
	$(VENV)/playwright install chromium
	mkdir -p documents

test:
	$(VENV)/python -m pytest tests/ -q

smoke:
	$(VENV)/python scripts/smoke_test.py

handshake:
	$(VENV)/python scripts/mcp_handshake.py

licenses:
	$(VENV)/python scripts/gen_licenses.py > THIRD_PARTY_LICENSES.md
	@echo "wrote THIRD_PARTY_LICENSES.md"

clean:
	rm -rf documents/*.pdf documents/*.md documents/*.docx
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
