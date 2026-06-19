"""Terminal entry point for the evidence-review pipeline.

Full orchestration lands in MVP-8. This stub keeps the AGENTS.md-mandated entry
point importable and runnable. The bootstrap puts the ``code/`` source root on the
path so ``python code/main.py`` works from anywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent  # the code/ source root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    print("evidence-review pipeline: runner lands in MVP-8 (see TASKS.md).")


if __name__ == "__main__":
    main()
