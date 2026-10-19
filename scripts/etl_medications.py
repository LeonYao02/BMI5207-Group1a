#!/usr/bin/env python3
"""Run from the repository root; no package installation is needed."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bmi5207.medications import main

if __name__ == "__main__":
    raise SystemExit(main())
