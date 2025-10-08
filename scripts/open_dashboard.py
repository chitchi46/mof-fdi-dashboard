#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
import subprocess

# Ensure local src/ is importable when running from repo root
_HERE = os.path.dirname(__file__)
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mof_investviz.ui import serve_build_dir, write_index_html
import glob


def _find_csvs(input_path: str):
    if os.path.isdir(input_path):
        return sorted(glob.glob(os.path.join(input_path, "*.csv")))
    return [input_path]


def _open_browser(url: str) -> None:
    try:
        ok = webbrowser.open(url, new=2)
        if ok:
            return
    except Exception:
        pass
    # fallbacks commonly available on WSL/desktop Linux
    for cmd in (['wslview', url], ['xdg-open', url], ['/mnt/c/Windows/explorer.exe', url]):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            continue
    print(f"Open your browser to: {url}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Open dashboard for upload-based analysis (no preloading)")
    ap.add_argument("--build-dir", "-b", default="build", help="Build output dir (default: build)")
    ap.add_argument("--host", default="0.0.0.0", help="Host/IP to bind (default: 0.0.0.0)")
    ap.add_argument("--port", "-p", type=int, default=8000, help="Port (default: 8000)")
    args = ap.parse_args()

    os.makedirs(args.build_dir, exist_ok=True)
    write_index_html(args.build_dir)

    # Serve in a thread
    t = threading.Thread(target=serve_build_dir, args=(args.build_dir, args.host, args.port), daemon=True)
    t.start()
    time.sleep(1.0)  # give server a moment

    # Open browser to localhost (works in most WSL setups)
    url = f"http://localhost:{args.port}/"
    _open_browser(url)
    print(f"Dashboard served at {url} (host={args.host}) — upload a CSV to analyze. Ctrl+C to stop.")
    try:
        while t.is_alive():
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
