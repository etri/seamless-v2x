"""Compatibility entry point for the 2026-10-08 core replay release.

Previous speed-conditioned scripts remain in repository history at commit
8400a6e184286d73697f3eb5bd67bf7c6939d474. See README.md for scope.
"""

from pathlib import Path
import sys
from revision20261008 import main


if __name__ == "__main__":
    defaults = []
    raise SystemExit(main(defaults + sys.argv[1:]))
