"""Writes the API's OpenAPI schema to a file, for the frontend's generated client."""

import json
import sys
from pathlib import Path

from app.main import app

Path(sys.argv[1]).write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
