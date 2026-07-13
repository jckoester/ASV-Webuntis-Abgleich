# ASV ↔ WebUntis Abgleich

Liest die Schüler-↔-Schülergruppen-Zuordnung aus **ASV** (datenführend) und
gleicht sie **read-only** gegen den Ist-Zustand in **WebUntis** ab, um Abweichungen
als konkrete Abarbeitungsliste zu melden. Konzept und Phasenpläne liegen im
PKM-Vault (`Projekte/ASV-webUntis-Abgleich`).

## Stand

- **Phase 0** (API-Spike) abgeschlossen: Fetcher-Endpunkt validiert —
  `GET api.webuntis.com/WebUntis/api/rest/extern/v1/lesson?start=&end=` (ISO-Datum),
  Auth via Client-Credentials. Join über `externKey` (== ASV-Schüler-ID).
- **Phase 1** (ASV-Parser) fertig — `asv_webuntis/parser.py`, 289 Schülergruppen
  aus dem Export, 19 Tests grün.
- **Phase 2** (WebUntis-Fetcher) gebaut — `asv_webuntis/fetcher.py`, Ist-Zustand
  read-only aus `/lesson` mit lokalem Cache.
- **Phase 3** (Abgleich/Diff) Kern gebaut — `asv_webuntis/diff.py` +
  `abgleich.py`. Befund: Gruppen-Namensräume ASV↔WebUntis disjunkt → Auto-Mapper
  als nächstes.

## Struktur

- `asv_webuntis/parser.py` — ASV-Export → `Record(schueler_key, gruppe, fach, …)`.
- `asv_webuntis/fetcher.py` — WebUntis-Ist → `Ist(extern_key, studentgroup, von, bis)`.
- `asv_webuntis/diff.py` — Soll↔Ist-Diff → `Finding(art, schueler_key, gruppe)`.
- `asv_webuntis/abgleich.py` — CLI: Parser + Fetcher + Diff, kategorisierter Report.
- `asv_webuntis/inspect_export.py` — Export sezieren (Encoding/Spalten erkennen).
- `tests/` — Unit-Tests: `python3 -m unittest discover -s tests -t .`
- `spike/` — Wegwerf-Spikes aus Phase 0 (dokumentiert, können entfernt werden).

## Workflow Phase 1

```
python3 -m asv_webuntis.inspect_export asv_export.csv     # Spalten identifizieren
# dann in Code:
#   from asv_webuntis.parser import parse_export
#   parse_export(path, key_col=…, groups_col=…, klasse_col=…, delimiter=…, encoding=…)
```

## Datenschutz

`.env`, `asv_export.csv`, `data/`, `spike/out/` sind gitignored — sie enthalten
Zugangsdaten bzw. personenbezogene Daten. Nie committen.
