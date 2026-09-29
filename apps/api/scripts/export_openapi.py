"""Dumps the OpenAPI document. Usage: APP_ENV=test uv run python scripts/export_openapi.py > openapi.json"""

import json
import sys

from app.main import create_app

json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
