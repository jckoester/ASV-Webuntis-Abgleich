"""ASV-Parser (Phase 1).

Wandelt den ASV-Export in normalisierte Records ``(schueler_key, gruppe, fach,
art, rest)``. `gruppe` ist der Token, der gegen die WebUntis-`studentgroups`
joint. Read-only, reines stdlib. Konzept/Testfälle: PKM `Phase-1.md`.

Zwei Ebenen, immun gegen Slash/Komma im Klartext:
  1. `split_entries` — trennt am Komma VOR dem nächsten Kürzel, nicht am nackten.
  2. `classify_entry` — ordnet jeden Eintrag einer der vier realen Formen zu.

Reale Eintragsformen (an echtem Export belegt, Phase-1-Ergebnis.md):
  Sek I      FACH/GRUPPE[/SCHIENE]/Klartext   REV/Re82/1/…      → gruppe=field[1]
  ganze Kl.  FACH/KLASSE[/SCHIENE]/Klartext   BIO_1/8D/1/…      → verworfen
  Kursstufe  CODE/Klartext                    D[3,00]_1.2_2/…   → gruppe=field[0]
  POOL       POOL_x/KLASSE/SCHIENE/Klartext   POOL_8Na/8D/2/…   → gruppe=field[0]
  AG         Name/Klartext (ohne '[')         Band/…            → verworfen (Scope)
"""
from __future__ import annotations

import csv
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

# Spaltennamen des realen ASV-Exports (Phase 1, Schritt 1).
COL_KEY = "ID"
COL_GROUPS = ("besuchter Unterricht des Schülers/der Schülerin "
              "mit Bezeichnung, Fach, Lehrer")

# Komma + optionaler Whitespace VOR dem nächsten Kürzel. Kürzel beginnt mit
# Großbuchstabe, dann Buchstaben (auch klein: NwT), Ziffern, _ - . und – für
# Kursstufe D[5,00]_1.1_1 – auch [ ] und Komma, dann "/". Der Komma-in-[5,00]
# löst keinen Split aus, weil danach eine Ziffer (kein Großbuchstabe) folgt.
_ENTRY_SEP = re.compile(r",\s*(?=[A-ZÄÖÜ][A-Za-zÄÖÜäöü0-9_.,\[\]\-]*/)")

# Klassenname (5A–10E). Gruppe == Klasse → ganze Klasse, keine Schülergruppe.
_KLASSE = re.compile(r"^(?:[5-9]|10)[A-E]$")


def _default_is_klasse(token: str) -> bool:
    return bool(_KLASSE.match(token))


@dataclass(frozen=True)
class Record:
    """Eine Schüler↔Schülergruppe-Zuordnung.

    `gruppe` joint gegen WebUntis-`studentgroups`; `fach` = Fachkürzel (Sek I)
    bzw. Basis-Fach (Kursstufe) bzw. Code (POOL); `art` = Herkunftsform;
    `rest` = verbatim Klartext/Schiene/Lehrer (ungeparst, Kontext für Phase 3).
    """
    schueler_key: str
    gruppe: str
    fach: str
    art: str
    rest: str = ""


def split_entries(groups: str) -> list[str]:
    """Konkatenierte Gruppenliste → einzelne Einträge (getrimmt, ohne Leere)."""
    if not groups:
        return []
    return [e.strip() for e in _ENTRY_SEP.split(groups) if e.strip()]


def classify_entry(
    entry: str,
    is_klasse: Callable[[str], bool] | None = None,
) -> tuple[str, str, str, str] | None:
    """Ein Eintrag → (gruppe, fach, art, rest) oder None (verworfen: ganze
    Klasse / AG / Schrott). Siehe Formtabelle im Modul-Docstring."""
    is_klasse = is_klasse or _default_is_klasse
    raw = entry.split("/")  # NICHT feldweise strippen — rest bleibt verbatim
    if len(raw) < 2:
        return None
    feld0 = raw[0].strip()
    if not feld0:
        return None
    rest = ("/".join(raw[2:]) if len(raw) >= 3 else raw[1]).strip()

    if "[" in feld0:  # Kursstufe: Gruppe = ganzer Code, Fach = Präfix vor '['
        return feld0, feld0.split("[")[0].rstrip("_ "), "kursstufe", rest
    if feld0.startswith("POOL"):  # Pool-Gruppe: Gruppe = field[0]
        return feld0, feld0, "pool", rest
    if len(raw) == 2:  # weder Kursstufe noch POOL, nur 2 Felder → AG
        return None
    if " " in feld0:  # mehrwortiges field[0] → AG-Name (Fachkürzel haben keine Leerz.)
        return None
    feld1 = raw[1].strip()
    # ganze Klasse, leer, oder AG-Klartext (Gruppennamen haben keine Leerzeichen) → raus
    if not feld1 or " " in feld1 or is_klasse(feld1):
        return None
    return feld1, feld0, "sek1", rest  # Sek-I-Klappgruppe: Gruppe = field[1]


def parse_row(
    schueler_key: str,
    groups: str,
    is_klasse: Callable[[str], bool] | None = None,
) -> list[Record]:
    """Eine Schülerzeile → Records (klassifiziert, ohne Dedup)."""
    out: list[Record] = []
    for entry in split_entries(groups):
        classified = classify_entry(entry, is_klasse)
        if classified is not None:
            out.append(Record(schueler_key, *classified))
    return out


def dedupe(records: Iterable[Record]) -> list[Record]:
    """Reihenfolge-erhaltende Deduplizierung (Record ist hashbar)."""
    return list(dict.fromkeys(records))


def parse_export(
    path: str | Path,
    *,
    key_col: str = COL_KEY,
    groups_col: str = COL_GROUPS,
    delimiter: str = ";",
    encoding: str = "utf-8-sig",
    is_klasse: Callable[[str], bool] | None = None,
) -> list[Record]:
    """ASV-Export (CSV) → deduplizierte, klassifizierte Records."""
    records: list[Record] = []
    with open(path, encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        _require_cols(reader.fieldnames, key_col, groups_col)
        for row in reader:
            key = (row.get(key_col) or "").strip()
            if key:
                records.extend(parse_row(key, row.get(groups_col) or "", is_klasse))
    return dedupe(records)


def _require_cols(fieldnames: Iterable[str] | None, *cols: str) -> None:
    have = set(fieldnames or ())
    missing = [c for c in cols if c not in have]
    if missing:
        raise ValueError(
            f"Spalten fehlen im Export: {missing}. Vorhanden: {sorted(have)}")
