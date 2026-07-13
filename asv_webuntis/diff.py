"""Abgleich-Diff (Phase 3, Kern) — ASV-Soll gegen WebUntis-Ist.

Rein & testbar, nur stdlib. Vergleicht zwei Mengen von `(schueler_key, gruppe)`
und kategorisiert jede Abweichung (Kategorien laut Plan):

  FEHLT_IN_WU        in ASV, nicht in WebUntis → Häkchen setzen (mit Von-Datum)
  ZUVIEL_IN_WU       in WebUntis, nicht in ASV → Bis-Datum setzen (nicht löschen)
  GRUPPE_UNBEKANNT   ASV-Gruppe ohne WebUntis-Pendant → Stundenplaner / Mapping
  SCHUELER_UNBEKANNT ASV-ID nicht in WebUntis → Stammdaten-Sync prüfen
"""
from __future__ import annotations

import collections
import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

CATEGORIES = ("FEHLT_IN_WU", "ZUVIEL_IN_WU", "GRUPPE_UNBEKANNT", "SCHUELER_UNBEKANNT")

Pair = tuple[str, str]


@dataclass(frozen=True)
class Finding:
    art: str
    schueler_key: str
    gruppe: str  # ASV-Gruppenname (bzw. WebUntis-Name bei ZUVIEL_IN_WU)


def diff(
    asv_pairs: Iterable[Pair],
    ist_pairs: Iterable[Pair],
    wu_groups: Iterable[str],
    wu_students: Iterable[str],
    mapping: Mapping[str, str] | None = None,
) -> list[Finding]:
    """Kategorisierter Diff. `mapping` übersetzt ASV-Gruppennamen → WebUntis-
    Namen (fehlt ein Eintrag, wird der ASV-Name unverändert verwendet)."""
    m = mapping or {}
    wu_groups = set(wu_groups)
    wu_students = set(wu_students)
    ist_pairs = set(ist_pairs)

    out: list[Finding] = []
    expected: set[Pair] = set()  # was ASV in WebUntis erwartet (gemappt)
    for s, g_asv in asv_pairs:
        g = m.get(g_asv, g_asv)
        expected.add((s, g))
        if s not in wu_students:
            out.append(Finding("SCHUELER_UNBEKANNT", s, g_asv))
        elif g not in wu_groups:
            out.append(Finding("GRUPPE_UNBEKANNT", s, g_asv))
        elif (s, g) not in ist_pairs:
            out.append(Finding("FEHLT_IN_WU", s, g_asv))

    for s, g_wu in ist_pairs:
        if (s, g_wu) not in expected:
            out.append(Finding("ZUVIEL_IN_WU", s, g_wu))
    return out


def summarize(findings: Iterable[Finding]) -> dict:
    findings = list(findings)
    counts = collections.Counter(f.art for f in findings)
    return {
        "counts": {c: counts.get(c, 0) for c in CATEGORIES},
        "gruppe_unbekannt": sorted({f.gruppe for f in findings
                                    if f.art == "GRUPPE_UNBEKANNT"}),
        "schueler_unbekannt": sorted({f.schueler_key for f in findings
                                      if f.art == "SCHUELER_UNBEKANNT"}),
    }


def load_mapping(path: str | Path) -> dict[str, str]:
    """Mapping-CSV `ASV-Gruppe;WebUntis-Gruppe` (Kommentare mit `#`)."""
    m: dict[str, str] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) >= 2 and row[0].strip() and not row[0].lstrip().startswith("#"):
                m[row[0].strip()] = row[1].strip()
    return m


def write_report(findings: Iterable[Finding], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Befund", "Schueler", "Gruppe"])
        for x in sorted(findings, key=lambda f: (f.art, f.gruppe, f.schueler_key)):
            w.writerow([x.art, x.schueler_key, x.gruppe])
