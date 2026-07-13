"""WebUntis-Fetcher (Phase 2) — read-only Ist-Zustand aus `extern/v1/lesson`.

Holt einen Client-Credentials-Token, ruft `/lesson` für einen Datumsbereich ab
(Endpunkt in Phase 0 validiert), **cacht die Rohantwort lokal** und flacht sie zu
Ist-Records `(extern_key, studentgroup, von, bis)` — dieselbe Schlüsselform wie
die Parser-Ausgabe (Phase 3 joint darüber). Nur stdlib, ausschließlich GET.

    python3 -m asv_webuntis.fetcher --stichtag 2026-06-15
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_TOKEN_PATH = "/WebUntis/api/sso/v3/{tenant}/token"
_LESSON_PATH = "/WebUntis/api/rest/extern/v1/lesson"


@dataclass(frozen=True)
class Ist:
    """Ein WebUntis-Ist-Eintrag: Schüler (extern_key) in Schülergruppe,
    Mitgliedschaft gültig von–bis (ISO-Datum, leer = unbegrenzt)."""
    extern_key: str
    studentgroup: str
    von: str = ""
    bis: str = ""


@dataclass(frozen=True)
class Credentials:
    tenant: str
    client_id: str
    secret: str
    token_base: str = "https://api.webuntis.com"
    api_base: str = "https://api.webuntis.com"


# ── Auth & HTTP ─────────────────────────────────────────────────────────

def load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def credentials_from_env(path: str = ".env") -> Credentials:
    load_env(path)
    tenant = os.environ.get("UNTIS_TENANT_ID", "").strip()
    client = os.environ.get("UNTIS_CLIENT_ID", "").strip()
    secret = os.environ.get("UNTIS_CLIENT_SECRET", "").strip()
    if not (tenant and client and secret):
        raise RuntimeError("UNTIS_TENANT_ID / UNTIS_CLIENT_ID / UNTIS_CLIENT_SECRET "
                           "fehlen (.env aus .env.example).")
    return Credentials(
        tenant, client, secret,
        os.environ.get("UNTIS_TOKEN_BASE", "https://api.webuntis.com").rstrip("/"),
        os.environ.get("UNTIS_API_BASE", "https://api.webuntis.com").rstrip("/"),
    )


def _http(req: urllib.request.Request) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def get_token(cred: Credentials) -> str:
    url = (f"{cred.token_base}{_TOKEN_PATH.format(tenant=urllib.parse.quote(cred.tenant))}"
           f"?grant_type=client_credentials")
    basic = base64.b64encode(f"{cred.client_id}:{cred.secret}".encode()).decode()
    req = urllib.request.Request(
        url, data=b"grant_type=client_credentials", method="POST",
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"})
    status, body = _http(req)
    if status != 200:
        raise RuntimeError(f"Token-Call {status}: {body}")
    token = json.loads(body).get("access_token")
    if not token:
        raise RuntimeError(f"Kein access_token: {body}")
    return token


def fetch_lessons(
    cred: Credentials | None,
    start: str,
    end: str,
    *,
    cache_dir: str | Path = "data/cache",
    refresh: bool = False,
) -> dict:
    """Rohantwort von `/lesson?start&end`. Nutzt lokalen Cache (gitignored),
    außer `refresh=True`. `cred=None` + vorhandener Cache → kein API-Zugriff
    (Credentials werden nur bei Cache-Miss lazy aus .env geladen)."""
    cache = Path(cache_dir) / f"lesson_{start}_{end}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    token = get_token(cred or credentials_from_env())
    url = (f"{cred.api_base}{_LESSON_PATH}?"
           + urllib.parse.urlencode({"start": start, "end": end}))
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/json"})
    status, body = _http(req)
    if status != 200:
        raise RuntimeError(f"/lesson {status}: {body[:300]}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(body, encoding="utf-8")
    return json.loads(body)


# ── Flatten & Stichtag (rein, testbar ohne API) ─────────────────────────

def lessons_to_ist(raw: dict) -> list[Ist]:
    """`/lesson`-Rohantwort → Ist-Records. Lessons ohne Schülergruppe (ganze
    Klasse) werden übersprungen; Mitgliedschaftsdaten aus `assignments`."""
    out: list[Ist] = []
    for lesson in raw.get("lessons") or []:
        groups = [g.get("shortName") for g in (lesson.get("studentgroups") or [])
                  if g.get("shortName")]
        if not groups:
            continue
        for st in lesson.get("students") or []:
            key = st.get("externKey")
            if not key:
                continue
            for a in (st.get("assignments") or [{}]):
                von = a.get("start") or lesson.get("start") or ""
                bis = a.get("end") or lesson.get("end") or ""
                for g in groups:
                    out.append(Ist(key, g, von, bis))
    return out


def all_studentgroups(raw: dict) -> set[str]:
    """Alle in WebUntis bekannten Schülergruppen-Namen (auch ohne aktive
    Mitglieder), für die GRUPPE_UNBEKANNT-Erkennung im Diff."""
    return {g.get("shortName") for lesson in raw.get("lessons") or []
            for g in (lesson.get("studentgroups") or []) if g.get("shortName")}


def all_students(raw: dict) -> set[str]:
    """Alle in den Lessons vorkommenden Schüler (externKey)."""
    return {st.get("externKey") for lesson in raw.get("lessons") or []
            for st in (lesson.get("students") or []) if st.get("externKey")}


def ist_at(records: Iterable[Ist], stichtag: str) -> set[tuple[str, str]]:
    """(extern_key, studentgroup) für Mitgliedschaften, die am `stichtag`
    (ISO) aktiv sind: von <= stichtag <= bis (leere Grenze = offen)."""
    return {(r.extern_key, r.studentgroup) for r in records
            if (not r.von or r.von <= stichtag) and (not r.bis or stichtag <= r.bis)}


def week_range(stichtag_iso: str) -> tuple[str, str]:
    """Mo–Fr der Woche, in der `stichtag` liegt (ISO). Ein Tag zeigt nur die
    Gruppen mit Unterricht an *dem* Tag; die Woche zählt alle auf."""
    d = datetime.date.fromisoformat(stichtag_iso)
    monday = d - datetime.timedelta(days=d.weekday())
    return monday.isoformat(), (monday + datetime.timedelta(days=4)).isoformat()


# ── CLI ─────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    today = datetime.date.today().isoformat()
    ap = argparse.ArgumentParser(description="WebUntis Ist-Zustand (read-only).")
    ap.add_argument("--stichtag", default=today, help="ISO-Datum (Default heute)")
    ap.add_argument("--woche", action="store_true",
                    help="ganze Woche (Mo–Fr) des Stichtags abrufen — zählt alle Gruppen auf")
    ap.add_argument("--start", help="ISO-Datum (überschreibt --woche)")
    ap.add_argument("--end", help="ISO-Datum (überschreibt --woche)")
    ap.add_argument("--refresh", action="store_true", help="Cache umgehen")
    a = ap.parse_args(argv)
    if a.start and a.end:
        start, end = a.start, a.end
    elif a.woche:
        start, end = week_range(a.stichtag)
    else:
        start = end = a.stichtag

    try:
        cred = credentials_from_env()
        raw = fetch_lessons(cred, start, end, refresh=a.refresh)
    except RuntimeError as e:
        sys.exit(f"✗ {e}")

    ist = lessons_to_ist(raw)
    aktiv = ist_at(ist, a.stichtag)
    n_less = len(raw.get("lessons") or [])
    print(f"Zeitraum {start}–{end} | Lessons: {n_less} | Ist-Records: {len(ist)}")
    print(f"Am Stichtag {a.stichtag} aktiv: {len(aktiv)} (Schüler,Gruppe)-Paare "
          f"| distinct Gruppen: {len({g for _, g in aktiv})} "
          f"| distinct Schüler: {len({k for k, _ in aktiv})}")
    beispiel = sorted({g for _, g in aktiv})[:12]
    print(f"Beispiel-Gruppen: {beispiel}")
    if n_less == 0:
        print("⚠ 0 Lessons — evtl. Ferientag? --stichtag auf einen Unterrichtstag setzen.")


if __name__ == "__main__":
    main()
