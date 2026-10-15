"""CLI of the DS2 contract: request JSON file (or stdin) -> response on stdout.

    python -m src.legal_retrieval.contract.cli --demo
    python -m src.legal_retrieval.contract.cli request.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .handler import _demo, handle


def main() -> None:
    """Read a request, print the response (UTF-8, Arabic kept readable)."""
    parser = argparse.ArgumentParser(description="DS2 legal retrieval contract")
    parser.add_argument("request", nargs="?", type=Path, help="request JSON file")
    parser.add_argument("--demo", action="store_true", help="use the demo request")
    args = parser.parse_args()

    if args.demo:
        request = _demo()["request"]
    elif args.request:
        request = json.loads(args.request.read_text(encoding="utf-8"))
    else:
        request = json.load(sys.stdin)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console
    print(json.dumps(handle(request), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
