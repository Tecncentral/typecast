"""Compatibility entry point; the authoritative pair-grain builder is data.build_join.

The join now contains every property/model pair, replacing the old separate
property_models table. Both script and module invocation remain supported.
"""
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.build_join import build_join as build, main

if __name__ == "__main__":
    raise SystemExit(main())
