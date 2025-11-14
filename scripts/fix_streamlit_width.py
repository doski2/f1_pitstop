from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}
PY_GLOB = "**/*.py"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}
PY_GLOB = "**/*.py"

PAT_TRUE = re.compile(r"\buse_container_width\s*=\s*True\b")
PAT_FALSE = re.compile(r"\buse_container_width\s*=\s*False\b")


def should_skip(p: Path) -> bool:
    parts = set(p.parts)
    return any(x in EXCLUDE_DIRS for x in parts)


def transform_line(line: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if "use_container_width" not in line:
        return line, notes
    # Evita colisiones si ya hay 'width=' en la misma llamada
    if "width=" in line:
        notes.append("detectado width= en la misma línea; revisar manualmente")
        return line, notes
    new_line = PAT_TRUE.sub("width='stretch'", line)
    new_line = PAT_FALSE.sub("width='content'", new_line)
    # Si quedó 'use_container_width' sin True/False explícito, avisar
    if "use_container_width" in new_line:
        notes.append("uso no estándar de use_container_width; revisar manualmente")
    return new_line, notes


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Migrar use_container_width → width ('stretch'|'content')"
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Escribir cambios en disco (por defecto solo vista previa)",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    changed = 0
    manual = []

    for path in root.glob(PY_GLOB):
        if should_skip(path):
            continue
        original = path.read_text(encoding="utf-8")
        out_lines = []
        file_manual_notes = []
        mutated = False
        for i, line in enumerate(original.splitlines(keepends=True), start=1):
            new, notes = transform_line(line)
            if new != line:
                mutated = True
            if notes:
                file_manual_notes.append((i, line.rstrip("\n"), notes))
            out_lines.append(new)

        if mutated:
            changed += 1
            print(f"[mod] {path}")
            if args.apply:
                bak = path.with_suffix(path.suffix + ".bak")
                if not bak.exists():
                    bak.write_text(original, encoding="utf-8")
                path.write_text("".join(out_lines), encoding="utf-8")
        if file_manual_notes:
            for ln, src, notes in file_manual_notes:
                manual.append((path, ln, src, notes))

    if manual:
        print("\n[AVISOS] Revisar manualmente estas líneas:")
        for p, ln, src, notes in manual:
            print(f" - {p}:{ln}: {src}")
            for n in notes:
                print(f"     • {n}")

    print(
        f"\nHecho. Archivos modificados: {changed}. {'(vista previa)' if not args.apply else ''}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
