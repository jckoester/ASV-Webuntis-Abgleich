"""Auto-Mapper (Phase 3) — schlägt ASV-Gruppe ↔ WebUntis-Gruppe über die
**Mitglieder-Überlappung** vor: zwei Namen derselben realen Gruppe teilen die
Schülermenge. Das umgeht LK/Basis (Groß/klein), Kurshalbjahr, Lehrerkürzel-
Matching und die disjunkten Namensräume komplett. Nur stdlib.

    python3 -m asv_webuntis.mapper --start 2025-11-17 --end 2025-11-21 \
            --stichtag 2025-11-17 [--write data/mapping.csv --min-jaccard 0.7]
"""
from __future__ import annotations

import argparse
import collections
import datetime
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass

from . import fetcher
from . import parser as asvparser

Pair = tuple[str, str]


@dataclass(frozen=True)
class Proposal:
    asv_gruppe: str
    wu_gruppen: tuple[str, ...]   # 1+ Zielgruppen (jahrgangsübergreifend: mehrere)
    abdeckung: float              # abgedeckte ASV-Schüler / ASV-Größe
    asv_size: int


def members(pairs: Iterable[Pair]) -> dict[str, set[str]]:
    d: dict[str, set[str]] = collections.defaultdict(set)
    for s, g in pairs:
        d[g].add(s)
    return d


def _stem(name: str) -> str:
    """Fach-Stamm = führende Buchstaben (case-sensitiv wg. LK/Basis):
    `BK_11`→`BK`, `bk1_12`→`bk`, `evr1_11`→`evr`."""
    m = re.match(r"[A-Za-zÄÖÜäöü]+", name)
    return m.group() if m else name


def cover(gm: set[str], wu_members: dict[str, set[str]],
          min_precision: float = 0.5) -> tuple[list[str], set[str]]:
    """Greedy Set-Cover: sammle WU-Gruppen, die **mehrheitlich in** `gm` liegen
    (Precision ≥ min_precision), bis `gm` abgedeckt ist. Zusätzliche Zielgruppen
    müssen den **Fach-Stamm** der ersten teilen (jahrgangsübergreifend = dasselbe
    Fach über Stufen; verhindert Misch-Matches wie Geschichte+Religion).
    1 Ziel für Normalkurse, 2 für jahrgangsübergreifende; POOL deckt so nicht voll."""
    targets: list[str] = []
    covered: set[str] = set()
    stem: str | None = None
    while covered < gm:
        best: tuple[str, int, set[str]] | None = None
        for h, hm in wu_members.items():
            if h in targets or (stem is not None and _stem(h) != stem):
                continue
            inter = gm & hm
            gain = len(inter - covered)
            if not gain or len(inter) / len(hm) < min_precision:
                continue
            if best is None or gain > best[1]:
                best = (h, gain, inter)
        if best is None:
            break
        targets.append(best[0])
        covered |= best[2]
        if stem is None:
            stem = _stem(best[0])
    return targets, covered


def propose(asv_pairs: Iterable[Pair], ist_pairs: Iterable[Pair],
            *, min_precision: float = 0.5) -> list[Proposal]:
    """Je ASV-Gruppe die Zielgruppen (Set-Cover). Konfidenz = Abdeckung."""
    wu_m = members(ist_pairs)
    out: list[Proposal] = []
    for g, gm in members(asv_pairs).items():
        targets, covered = cover(gm, wu_m, min_precision)
        if targets:
            out.append(Proposal(g, tuple(targets), round(len(covered) / len(gm), 3), len(gm)))
    return out


def _resolve_range(a) -> tuple[str, str]:
    if a.start and a.end:
        return a.start, a.end
    if a.woche:
        return fetcher.week_range(a.stichtag)
    return a.stichtag, a.stichtag


def main(argv: list[str] | None = None) -> None:
    today = datetime.date.today().isoformat()
    ap = argparse.ArgumentParser(description="Auto-Mapper ASV↔WebUntis (read-only).")
    ap.add_argument("--asv", default="asv_export.csv")
    ap.add_argument("--stichtag", default=today)
    ap.add_argument("--woche", action="store_true")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--write", help="Mapping-CSV schreiben (asv;wu[,wu]) ab --min-abdeckung")
    ap.add_argument("--min-abdeckung", type=float, default=0.9)
    ap.add_argument("--max-targets", type=int, default=4,
                    help="max. Zielgruppen je ASV-Gruppe (mehr = POOL-Streuung → nicht schreiben)")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args(argv)
    start, end = _resolve_range(a)

    asv_pairs = {(r.schueler_key, r.gruppe) for r in asvparser.parse_export(a.asv)}
    try:
        raw = fetcher.fetch_lessons(None, start, end, refresh=a.refresh)
    except RuntimeError as e:
        sys.exit(f"✗ {e}")
    ist_pairs = fetcher.ist_at(fetcher.lessons_to_ist(raw), a.stichtag)

    proposals = propose(asv_pairs, ist_pairs)
    n_asv = len({g for _, g in asv_pairs})
    matched = {p.asv_gruppe for p in proposals}
    # >MAX_TARGETS Zielgruppen = Streuung (POOL) → nicht als Mapping schreiben
    MAX_TARGETS = a.max_targets

    def gut(p):
        return p.abdeckung >= a.min_abdeckung and len(p.wu_gruppen) <= MAX_TARGETS

    buckets = collections.Counter()
    for p in proposals:
        buckets["1.0 (perfekt)" if p.abdeckung >= 1.0 else
                "0.9–1.0" if p.abdeckung >= 0.9 else
                "0.7–0.9" if p.abdeckung >= 0.7 else
                "0.5–0.7" if p.abdeckung >= 0.5 else "<0.5"] += 1
    mehrfach = [p for p in proposals if 1 < len(p.wu_gruppen) <= MAX_TARGETS]
    streuung = [p for p in proposals if len(p.wu_gruppen) > MAX_TARGETS]
    print(f"ASV-Gruppen: {n_asv} | mit Kandidat: {len(proposals)} | "
          f"ohne Überlappung: {n_asv - len(matched)}")
    print(f"Abdeckung-Verteilung: {dict(buckets)}")
    print(f"davon jahrgangsübergreifend (2–{MAX_TARGETS} Ziele): {len(mehrfach)} | "
          f"Streuung (>{MAX_TARGETS}, z. B. POOL): {len(streuung)}\n")

    print(f"Jahrgangsübergreifende Kurse (Beispiele):")
    for p in sorted(mehrfach, key=lambda p: -len(p.wu_gruppen))[:8]:
        print(f"  {p.abdeckung:>5} {p.asv_gruppe:18s} → {', '.join(p.wu_gruppen)}")
    unsicher = sorted((p for p in proposals if not gut(p) and len(p.wu_gruppen) <= MAX_TARGETS),
                      key=lambda p: p.abdeckung)
    print(f"\nHandprüfung (Abdeckung < {a.min_abdeckung}): {len(unsicher)}")
    for p in unsicher:
        print(f"  {p.abdeckung:>5} {p.asv_gruppe:18s} → {', '.join(p.wu_gruppen)} "
              f"(ASV n={p.asv_size})")
    print(f"Streuung/POOL ({len(streuung)}): {sorted(p.asv_gruppe for p in streuung)}")

    if a.write:
        good = [p for p in proposals if gut(p)]
        from pathlib import Path
        Path(a.write).parent.mkdir(parents=True, exist_ok=True)
        with open(a.write, "w", encoding="utf-8", newline="") as f:
            f.write(f"# ASV-Gruppe;WebUntis-Gruppe[,…] (auto, Abdeckung>={a.min_abdeckung})\n")
            for p in sorted(good, key=lambda p: p.asv_gruppe):
                f.write(f"{p.asv_gruppe};{','.join(p.wu_gruppen)}\n")
        print(f"\nGeschrieben: {a.write} ({len(good)} Zeilen)")


if __name__ == "__main__":
    main()
