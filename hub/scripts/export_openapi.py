# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Export the hub's OpenAPI schema to ``shared/openapi.yaml``.

Run after changing any route/model so the Flutter client stays in lockstep:

    python scripts/export_openapi.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.config import REPO_ROOT
from app.main import app


def main() -> None:
    schema = app.openapi()
    out = REPO_ROOT / "shared" / "openapi.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(schema, fh, sort_keys=False, allow_unicode=True)
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
