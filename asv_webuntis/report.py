"""Lesbarer Abgleich-Report (Phase 4) — die Abarbeitungsliste.

Gruppiert die Befunde nach Schülergruppe: pro Gruppe, welche Schüler in WebUntis
fehlen (Häkchen setzen) bzw. zu viel sind (Bis-Datum). Strukturelle Befunde
(`GRUPPE_UNBEKANNT`, `GRUPPE_NUR_IN_WU`) getrennt für den Stundenplaner.
Enthält Klarnamen → nur lokal (data/, gitignored). Rein & stdlib.
"""
from __future__ import annotations

import collections
from collections.abc import Iterable, Mapping

from .diff import Finding


def render(
    findings: Iterable[Finding],
    mapping: Mapping[str, list[str]] | None,
    names: Mapping[str, str],
    wu_sizes: Mapping[str, int],
    stichtag: str,
    erzeugt: str = "",
    asv_ids: Iterable[str] | None = None,
) -> str:
    """Findings → lesbarer Report-Text (nach Gruppe gebündelt). `asv_ids` =
    Menge der ASV-Schüler; ZUVIEL-Schüler außerhalb davon (nur in WebUntis)
    werden separat ausgewiesen (Karteileichen / in ASV fehlend)."""
    m = mapping or {}
    asv_set = set(asv_ids) if asv_ids is not None else set(names)

    def nm(key: str) -> str:
        return names.get(key, key)

    def ziel(g: str) -> str:
        t = m.get(g)
        return ", ".join(t) if isinstance(t, list) else (t or g)

    fehlt: dict[str, list[str]] = collections.defaultdict(list)
    zuviel: dict[str, list[str]] = collections.defaultdict(list)
    nur_wu: dict[str, set[str]] = collections.defaultdict(set)
    unbekannt: set[str] = set()
    phantom: set[str] = set()
    schueler: set[str] = set()
    for f in findings:
        if f.art == "FEHLT_IN_WU":
            fehlt[f.gruppe].append(f.schueler_key)
        elif f.art == "ZUVIEL_IN_WU":
            if f.schueler_key in asv_set:
                zuviel[f.gruppe].append(f.schueler_key)
            else:  # in WebUntis, aber nicht im ASV-Export
                nur_wu[f.schueler_key].add(f.gruppe)
        elif f.art == "GRUPPE_UNBEKANNT":
            unbekannt.add(f.gruppe)
        elif f.art == "GRUPPE_NUR_IN_WU":
            phantom.add(f.gruppe)
        elif f.art == "SCHUELER_UNBEKANNT":
            schueler.add(f.schueler_key)

    L: list[str] = ["═" * 64,
                    f"ASV ↔ WebUntis Abgleich — Report (Stichtag {stichtag})"]
    if erzeugt:
        L.append(f"erzeugt {erzeugt}")
    L.append("═" * 64)

    klicks = sum(len(v) for v in fehlt.values()) + sum(len(v) for v in zuviel.values())
    L.append(f"\n── ABARBEITUNGSLISTE — {klicks} Klicks in "
             f"{len(fehlt) + len(zuviel)} Gruppen ──")

    L.append("\nFEHLT in WebUntis — Häkchen setzen (mit Von-Datum):")
    for g in sorted(fehlt) or []:
        L.append(f"  {g}  →  WebUntis: {ziel(g)}")
        for k in sorted(fehlt[g], key=nm):
            L.append(f"      +  {nm(k)}")
    if not fehlt:
        L.append("  (keine)")

    L.append("\nZUVIEL in WebUntis — Bis-Datum setzen (NICHT löschen):")
    for g in sorted(zuviel):
        L.append(f"  {g}")
        for k in sorted(zuviel[g], key=nm):
            L.append(f"      −  {nm(k)}")
    if not zuviel:
        L.append("  (keine)")

    L.append(f"\nSchüler nur in WebUntis (nicht im ASV-Export) — Karteileiche in "
             f"WebUntis oder in ASV nachtragen ({len(nur_wu)}):")
    for k in sorted(nur_wu, key=nm):
        L.append(f"  {nm(k)}  →  {', '.join(sorted(nur_wu[k]))}")
    if not nur_wu:
        L.append("  (keine)")

    L.append("\n── FÜR DEN STUNDENPLANER (strukturell) ──")
    L.append(f"\nASV-Gruppe ohne WebUntis-Pendant ({len(unbekannt)}):")
    L.append("  " + (", ".join(sorted(unbekannt)) or "(keine)"))
    L.append(f"\nWebUntis-Gruppe ohne ASV-Pendant — Phantome prüfen ({len(phantom)}):")
    for g in sorted(phantom, key=lambda g: (-wu_sizes.get(g, 0), g)):
        L.append(f"  {g}  (n={wu_sizes.get(g, '?')})")
    if not phantom:
        L.append("  (keine)")

    L.append(f"\n── STAMMDATEN ──\n\nASV-ID nicht in WebUntis ({len(schueler)}):")
    L.append("  " + (", ".join(sorted(nm(k) for k in schueler)) or "(keine)"))

    return "\n".join(L) + "\n"
