"""Exporta openapi.json desde la app FastAPI.

Uso:
    python -m backend.scripts.export_openapi

Genera `frontend/src/api/openapi.json` con el esquema OpenAPI 3.1 de la API.
Ejecutar después de cambios en routers/ o schemas.py, antes de re-generar los
tipos TypeScript.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Añadir raíz del repo al path para que los imports funcionen.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402

OUTPUT = ROOT / "frontend" / "src" / "api" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(schema, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"OK: OpenAPI schema exportado a {OUTPUT.relative_to(ROOT)}")
    print(f"   Endpoints: {len(schema.get('paths', {}))}")
    print(f"   Schemas: {len(schema.get('components', {}).get('schemas', {}))}")


if __name__ == "__main__":
    main()
