"""Generate and verify causal asymmetric-EWMA predictions for the revision inputs.

Previous speed-conditioned scripts remain in repository history at commit
8400a6e184286d73697f3eb5bd67bf7c6939d474. See README.md for scope.
"""

from pathlib import Path
import sys
from revision20261008 import main


if __name__ == "__main__":
    defaults = ['--prediction-only']
    defaults += ["--output-dir", str(Path(__file__).resolve().parent / "revision20261008" / 'predictions_only')]
    raise SystemExit(main(defaults + sys.argv[1:]))
