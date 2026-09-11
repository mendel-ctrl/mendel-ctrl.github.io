#!/usr/bin/env bash
# Start the Casambi lighting web app. Run from the casambi/ directory.
set -euo pipefail
cd "$(dirname "$0")"

# Create/activate a virtualenv and install deps on first run.
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi

# Refresh the catalog if we've never discovered (needs a valid .env).
if [ ! -f devices.json ] && [ -z "${CASAMBI_APP_DEMO:-}" ]; then
  ./.venv/bin/python casambi_ctrl.py login
  ./.venv/bin/python casambi_ctrl.py discover
fi

exec ./.venv/bin/python app.py
