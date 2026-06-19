"""Schema / enum / row-count lint for an output CSV (MVP-3).

Usage: python code/tools/schema_lint.py <output_csv>
Exits non-zero if the file is not a valid submission.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path


def _ensure_path() -> None:
    root = Path(__file__).resolve().parent.parent  # the code/ source root
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def validate_file(path: Path, schema) -> list[str]:
    errors: list[str] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return ["file is empty"]
        if header != list(schema.OUTPUT_COLUMNS):
            return [f"header mismatch: {header}"]
        for line_no, row in enumerate(reader, start=2):
            if len(row) != len(schema.OUTPUT_COLUMNS):
                errors.append(
                    f"row {line_no}: expected {len(schema.OUTPUT_COLUMNS)} columns, got {len(row)}"
                )
                continue
            mapping = dict(zip(schema.OUTPUT_COLUMNS, row, strict=True))
            errors.extend(schema.row_errors(mapping, prefix=f"row {line_no}"))
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: python code/tools/schema_lint.py <output_csv>")
        return 2
    _ensure_path()
    from data import schema

    errors = validate_file(Path(args[0]), schema)
    if errors:
        print(f"SCHEMA LINT FAILED ({len(errors)} issue(s)):")
        for error in errors[:50]:
            print("  -", error)
        return 1
    print("schema lint OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
