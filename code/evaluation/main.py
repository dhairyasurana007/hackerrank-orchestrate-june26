"""Evaluation entry point.

Full evaluation harness lands in MVP-9 / FINAL-2. The bootstrap puts the ``code/``
source root on the path so ``python code/evaluation/main.py`` works from anywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent  # the code/ source root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    print("evidence-review evaluation: harness lands in MVP-9 (see TASKS.md).")


if __name__ == "__main__":
    main()
