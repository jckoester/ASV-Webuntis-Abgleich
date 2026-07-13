"""Export-Inspektor (Phase 1, Schritt 1 — „den echten Export sezieren").

Zeigt Encoding, Trennzeichen, Spalten und rät je Spalte, ob sie die Join-GUID,
eine Klasse oder die konkatenierte Gruppenliste enthält. Read-only, stdlib.

    python3 -m asv_webuntis.inspect_export data/asv_export.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# GUID-Form wie WebUntis-externKey, z. B. 8a314fa1-90df007e-0190-e036a07c-0df5
_GUID = re.compile(r"^[0-9a-fA-F]{6,}(?:-[0-9a-fA-F]+){2,}$")


def _guess_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,|\t").delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample else ""
        return max(";,|\t", key=first.count) if first else ";"


def _tag(values: list[str]) -> str:
    vals = [v for v in values if v]
    if not vals:
        return ""
    if all(_GUID.match(v) for v in vals):
        return "  ← GUID? (Join-Schlüssel == externKey)"
    if any("/" in v and "," in v for v in vals):
        return "  ← Gruppenliste?"
    if all(len(v) <= 4 and v[:1].isalnum() for v in vals):
        return "  ← Klasse?"
    return ""


def _load(path: str, encoding: str | None, delimiter: str | None, rows: int):
    encodings = [encoding] if encoding else ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    sample = None
    for enc in encodings:
        try:
            with open(path, encoding=enc, newline="") as f:
                sample = f.read(8192)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    if sample is None:
        sys.exit("Encoding nicht erkannt — mit --encoding angeben.")

    delimiter = delimiter or _guess_delimiter(sample)
    with open(path, encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        cols = reader.fieldnames or []
        sample_rows = []
        for i, row in enumerate(reader):
            if i >= rows:
                break
            sample_rows.append(row)
    return encoding, delimiter, cols, sample_rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="ASV-Export inspizieren (read-only).")
    ap.add_argument("path", nargs="?", default="asv_export.csv")
    ap.add_argument("--encoding")
    ap.add_argument("--delimiter")
    ap.add_argument("--rows", type=int, default=3)
    a = ap.parse_args(argv)

    if not Path(a.path).exists():
        sys.exit(f"Datei nicht gefunden: {a.path}")

    encoding, delimiter, cols, sample_rows = _load(a.path, a.encoding, a.delimiter, a.rows)

    print(f"Datei:        {a.path}")
    print(f"Encoding:     {encoding}")
    print(f"Trennzeichen: {delimiter!r}")
    print(f"Spalten ({len(cols)}):\n")
    for c in cols:
        vals = [(r.get(c) or "").strip() for r in sample_rows]
        beispiel = next((v for v in vals if v), "")
        print(f"  {c:32s} z. B. {beispiel[:52]!r}{_tag(vals)}")
    print(f"\n{len(sample_rows)} Beispielzeile(n) gelesen. Kandidaten oben prüfen, dann:")
    print("  from asv_webuntis.parser import parse_export")
    print("  parse_export(path, key_col=…, groups_col=…, klasse_col=…,")
    print(f"               delimiter={delimiter!r}, encoding={encoding!r})")


if __name__ == "__main__":
    main()
