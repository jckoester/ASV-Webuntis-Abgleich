"""Abgleich (Phase 3) — ASV-Soll vs. WebUntis-Ist, kategorisierter Diff.

Verdrahtet Parser (ASV) + Fetcher (WebUntis, nutzt Cache) + Diff. Read-only.
Zusammenfassung ist PII-schonend; der optionale `--report` (mit Schüler-IDs)
landet unter `data/` (gitignored).

    python3 -m asv_webuntis.abgleich --stichtag 2025-11-17 --woche
    python3 -m asv_webuntis.abgleich --start 2025-11-17 --end 2025-11-21 \
            --stichtag 2025-11-17 --report data/report.csv
"""
from __future__ import annotations

import argparse
import datetime
import sys

from . import diff as diffmod
from . import fetcher
from . import parser as asvparser


def main(argv: list[str] | None = None) -> None:
    today = datetime.date.today().isoformat()
    ap = argparse.ArgumentParser(description="ASV ↔ WebUntis Abgleich (read-only).")
    ap.add_argument("--asv", default="asv_export.csv")
    ap.add_argument("--stichtag", default=today)
    ap.add_argument("--woche", action="store_true", help="Mo–Fr der Stichtag-Woche")
    ap.add_argument("--start", help="ISO (überschreibt --woche)")
    ap.add_argument("--end", help="ISO (überschreibt --woche)")
    ap.add_argument("--mapping", help="Mapping-CSV ASV-Gruppe;WebUntis-Gruppe")
    ap.add_argument("--report", help="Befund-CSV schreiben (enthält IDs → data/)")
    ap.add_argument("--refresh", action="store_true", help="WebUntis-Cache umgehen")
    a = ap.parse_args(argv)

    if a.start and a.end:
        start, end = a.start, a.end
    elif a.woche:
        start, end = fetcher.week_range(a.stichtag)
    else:
        start = end = a.stichtag

    records = asvparser.parse_export(a.asv)
    asv_pairs = {(r.schueler_key, r.gruppe) for r in records}

    try:
        raw = fetcher.fetch_lessons(None, start, end, refresh=a.refresh)
    except RuntimeError as e:
        sys.exit(f"✗ {e}")
    ist = fetcher.ist_at(fetcher.lessons_to_ist(raw), a.stichtag)
    wu_groups = fetcher.all_studentgroups(raw)
    wu_students = fetcher.all_students(raw)

    mapping = diffmod.load_mapping(a.mapping) if a.mapping else {}
    findings = diffmod.diff(asv_pairs, ist, wu_groups, wu_students, mapping)
    s = diffmod.summarize(findings)

    def counts(pairs):
        return f"{len(pairs)} Paare, {len({g for _, g in pairs})} Gruppen, {len({k for k, _ in pairs})} Schüler"

    print(f"ASV-Soll:               {counts(asv_pairs)}")
    print(f"WebUntis-Ist ({a.stichtag}): {counts(ist)}  "
          f"[Zeitraum {start}–{end}, {len(wu_groups)} Gruppen bekannt]")
    print(f"Mapping-Einträge:       {len(mapping)}\n")

    print("Befunde:")
    for cat in diffmod.CATEGORIES:
        print(f"  {cat:20s} {s['counts'][cat]:>6}")
    ug = s["gruppe_unbekannt"]
    print(f"\nGRUPPE_UNBEKANNT: {len(ug)} distinct ASV-Gruppen ohne WebUntis-Pendant")
    print("  " + ", ".join(ug[:40]) + (" …" if len(ug) > 40 else ""))
    print(f"SCHUELER_UNBEKANNT: {len(s['schueler_unbekannt'])} Schüler")

    if a.report:
        diffmod.write_report(findings, a.report)
        print(f"\nReport geschrieben: {a.report} ({len(findings)} Befunde)")


if __name__ == "__main__":
    main()
