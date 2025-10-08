#!/usr/bin/env python3
"""Serve the interactive dashboard with upload capability."""
from __future__ import annotations

import argparse
import os
import sys

# Ensure local src/ is importable when running from repo root
_HERE = os.path.dirname(__file__)
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mof_investviz.ui import serve_build_dir, write_index_html


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve the interactive dashboard with upload capability")
    ap.add_argument("--build-dir", "-b", default="build", help="Build directory to serve")
    ap.add_argument("--host", default="0.0.0.0", help="Host/IP to bind (e.g., 0.0.0.0 for WSL)")
    ap.add_argument("--port", "-p", type=int, default=8000, help="Port")
    args = ap.parse_args()

    if not os.path.isdir(args.build_dir):
        os.makedirs(args.build_dir, exist_ok=True)
    
    # Write the latest dashboard HTML with upload capability
    write_index_html(args.build_dir)
    
    print(f"Starting dashboard server at http://{args.host}:{args.port}")
    print(f"Build directory: {os.path.abspath(args.build_dir)}")
    print("Press Ctrl+C to stop")
    
    serve_build_dir(args.build_dir, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
