from __future__ import annotations

import os
from typing import Dict


SCHEMA_VERSION = "0.1.0"


def schema_path_default() -> str:
    """Default path of schema.yaml within the project (root)."""
    return os.path.abspath(os.path.join(os.getcwd(), "schema.yaml"))


def copy_schema_to_build(build_dir: str, schema_path: str | None = None) -> str:
    """Copy schema.yaml to build dir for reference (no parsing)."""
    sp = schema_path or schema_path_default()
    if not os.path.exists(sp):
        return ""
    os.makedirs(build_dir, exist_ok=True)
    dest = os.path.join(build_dir, "schema.yaml")
    with open(sp, "rb") as src, open(dest, "wb") as dst:
        dst.write(src.read())
    return dest


def schema_meta() -> Dict[str, str]:
    return {"schema.version": SCHEMA_VERSION}

