"""CLI entry point for `python -m tools.translation_lint`."""

from __future__ import annotations

import sys

from tools.translation_lint.cli import main

if __name__ == "__main__":
    sys.exit(main())
