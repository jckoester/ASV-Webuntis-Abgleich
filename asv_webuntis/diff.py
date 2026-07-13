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

# Mapping-Ziel "-" = bewusst kein WebUntis-Pendant (strukturell geklärt, z. B.
# Poolstunden, die in WU als normale Fachstunden laufen) → nicht als Befund melden.
IGNORE = "-"

Pair = tuple[str, str]


@dataclass(frozen=True)
class Finding:
    art: str
    schueler_key: str
    gruppe: str  # ASV-Gruppenname (bzw. WebUntis-Name bei ZUVIEL_IN_WU)


def _targets(mapping: Mapping, g_asv: str) -> list[str]:
    """Zielgruppen einer ASV-Gruppe. Eins-zu-viele (jahrgangsübergreifende Kurse:
    ein ASV-Code → mehrere WU-Gruppen). Ohne Mapping: der ASV-Name selbst."""
    t = mapping.get(g_asv)
    if t is None:
        return [g_asv]
    return [t] if isinstance(t, str) else list(t)


def diff(
    asv_pairs: Iterable[Pair],
    ist_pairs: Iterable[Pair],
    wu_groups: Iterable[str],
    wu_students: Iterable[str],
    mapping: Mapping[str, str | list[str]] | None = None,
) -> list[Finding]:
    """Kategorisierter Diff. `mapping` übersetzt ASV-Gruppe → eine *oder mehrere*
    WebUntis-Gruppen; ein Schüler gilt als vorhanden, wenn er in **irgendeiner**
    Zielgruppe ist (deckt jahrgangsübergreifende Kurse ab)."""
    m = mapping or {}
    wu_groups = set(wu_groups)
    wu_students = set(wu_students)
    ist_pairs = set(ist_pairs)

    out: list[Finding] = []
    expected: set[Pair] = set()
    for s, g_asv in asv_pairs:
        targets = _targets(m, g_asv)
        if targets == [IGNORE]:  # bewusst kein WU-Pendant → überspringen
            continue
        for t in targets:
            expected.add((s, t))
        if s not in wu_students:
            out.append(Finding("SCHUELER_UNBEKANNT", s, g_asv))
            continue
        known = [t for t in targets if t in wu_groups]
        if not known:
            out.append(Finding("GRUPPE_UNBEKANNT", s, g_asv))
        elif not any((s, t) in ist_pairs for t in known):
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


def load_mapping(path: str | Path) -> dict[str, list[str]]:
    """Mapping-CSV `ASV-Gruppe;WU-Gruppe[,WU-Gruppe…]` (Kommentare mit `#`).
    Mehrere Zielgruppen komma-getrennt → jahrgangsübergreifende Kurse."""
    m: dict[str, list[str]] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) >= 2 and row[0].strip() and not row[0].lstrip().startswith("#"):
                targets = [t.strip() for t in row[1].split(",") if t.strip()]
                if targets:
                    m[row[0].strip()] = targets
    return m


def write_report(findings: Iterable[Finding], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Befund", "Schueler", "Gruppe"])
        for x in sorted(findings, key=lambda f: (f.art, f.gruppe, f.schueler_key)):
            w.writerow([x.art, x.schueler_key, x.gruppe])
