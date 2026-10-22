"""CLI entry point for `python -m tools.esfile`."""

from __future__ import annotations

import sys

from tools.esfile.cli import main

if __name__ == "__main__":
    sys.exit(main())
