#!/usr/bin/env python3
"""Wegwerf-Spike Phase 0 — read-only. Kernfrage Q1: trägt die Unterrichts-/
Lesson-API den **Schülergruppennamen** und die **Schülerliste** (mit externKey)?

Erkenntnis aus Lauf 1: `start`/`end` sind die richtigen Parameter von
`extern/v1/lesson` (nur das Format YYYYMMDD war falsch → jetzt ISO YYYY-MM-DD).
UI nennt die Unterrichtsgruppen `class-lessons` → als zweiten Slug mitprüfen.

Datum via UNTIS_DATE_FROM / UNTIS_DATE_TO (ISO oder YYYYMMDD) überschreibbar;
bei Ferien einen Schultag im laufenden Unterricht setzen. Nur stdlib.
"""
from __future__ import annotations

import base64
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RESOURCES = ["lesson", "class-lessons"]


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


def iso(s: str) -> str:
    """YYYYMMDD oder YYYY-MM-DD → YYYY-MM-DD."""
    d = re.sub(r"\D", "", s)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else s


def http(req: urllib.request.Request) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def die(msg: str) -> None:
    print(f"\n✗ {msg}", file=sys.stderr)
    sys.exit(1)


def structure(node: object) -> dict[str, str]:
    paths: dict[str, str] = {}

    def walk(n: object, prefix: str = "") -> None:
        if isinstance(n, dict):
            for k, v in n.items():
                walk(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(n, list):
            if n:
                walk(n[0], f"{prefix}[]")
            else:
                paths.setdefault(prefix + "[]", "· (leere Liste)")
        else:
            paths.setdefault(prefix, repr(n)[:70])

    walk(node)
    return paths


def get_token(token_base: str, tenant: str, client: str, secret: str) -> str:
    url = (f"{token_base}/WebUntis/api/sso/v3/{urllib.parse.quote(tenant)}"
           f"/token?grant_type=client_credentials")
    basic = base64.b64encode(f"{client}:{secret}".encode()).decode()
    req = urllib.request.Request(
        url, data=b"grant_type=client_credentials", method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    status, body = http(req)
    print(f"Token  POST …/sso/v3/{tenant}/token  →  {status}")
    if status != 200:
        die(f"Token-Call fehlgeschlagen ({status}):\n{body}")
    tok = json.loads(body)
    if not tok.get("access_token"):
        die(f"Kein access_token:\n{body}")
    print(f"       Bearer erhalten, expires_in={tok.get('expires_in')}s\n")
    return tok["access_token"]


def dump_hit(resource: str, params: dict, body: str) -> None:
    out = Path("spike/out")
    out.mkdir(parents=True, exist_ok=True)
    fname = out / f"extern_{resource}.json"
    fname.write_text(body, encoding="utf-8")
    print(f"\n✓ TREFFER  {resource}  {params}")
    print(f"  gespeichert: {fname}  ({len(body)} Bytes)")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("  (keine JSON-Antwort)")
        return
    print("\nStruktur (Feldpfad → Beispielwert):")
    for path, val in sorted(structure(data).items()):
        mark = "  ←?" if any(s in path.lower() for s in (
            "group", "gruppe", "student", "extern", "class", "name",
            "subject", "date", "valid", "begin", "end")) else ""
        print(f"  {path:50s} {val}{mark}")


def main() -> None:
    load_env()
    tenant = os.environ.get("UNTIS_TENANT_ID", "").strip()
    client = os.environ.get("UNTIS_CLIENT_ID", "").strip()
    secret = os.environ.get("UNTIS_CLIENT_SECRET", "").strip()
    token_base = os.environ.get("UNTIS_TOKEN_BASE", "https://api.webuntis.com").rstrip("/")
    api_base = os.environ.get("UNTIS_API_BASE", "https://api.webuntis.com").rstrip("/")
    if not (tenant and client and secret):
        die("UNTIS_TENANT_ID / UNTIS_CLIENT_ID / UNTIS_CLIENT_SECRET fehlen.")

    today = datetime.date.today()
    d_to = iso(os.environ.get("UNTIS_DATE_TO", today.strftime("%Y%m%d")))
    d_from = iso(os.environ.get("UNTIS_DATE_FROM",
                                (today - datetime.timedelta(days=7)).strftime("%Y%m%d")))
    print(f"Datumsbereich (ISO): {d_from}–{d_to} "
          f"(anpassbar via UNTIS_DATE_FROM/UNTIS_DATE_TO)\n")

    token = get_token(token_base, tenant, client, secret)

    def variants() -> list[dict]:
        return [
            {"start": d_from, "end": d_to},                         # ISO-Datum
            {"start": f"{d_from}T00:00:00", "end": f"{d_to}T23:59:59"},  # ISO-Zeit
            {},                                                     # bare → Param-Hinweis
        ]

    for resource in RESOURCES:
        print(f"── {resource}")
        url = f"{api_base}/WebUntis/api/rest/extern/v1/{resource}"
        for params in variants():
            full = url + (("?" + urllib.parse.urlencode(params)) if params else "")
            req = urllib.request.Request(full, headers={
                "Authorization": f"Bearer {token}", "Accept": "application/json"})
            status, body = http(req)
            q = urllib.parse.urlencode(params) if params else "(ohne Parameter)"
            print(f"  {status}  ?{q}")
            if status == 200:
                dump_hit(resource, params, body)
                print("\nQ1 Gruppenname?  Q4 Datum?  Q7 Namen vs ASV — s. Struktur oben.")
                return
            print(f"       {body[:220]}")
        print()

    die("Kein 200. Fehlertexte oben zeigen den erwarteten Parameter/Typ — "
        "dann in variants()/RESOURCES nachziehen.")


if __name__ == "__main__":
    main()
