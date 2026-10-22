#!/usr/bin/env python3
"""Anonymisation staging for all domains + OMOP PERSON/DEATH. Run from the repository root."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bmi5207.person import main

if __name__ == "__main__":
    raise SystemExit(main())
