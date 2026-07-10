#!/usr/bin/env python3
"""Wegwerf-Spike Phase 0 — read-only. Prüft, welche `extern`-Platform-Endpunkte
der vorhandene Token (IServ-Credential) lesen darf. IServ nutzt genau diese API
für seine Synchronisation → der Token sollte hier berechtigt sein, anders als bei
OneRoster.

Kein Fuzzing: getestet werden die *dokumentierten* Platform-API-Ressourcen
(Lessons, Student-/Class-Management), nur Singular/Plural-Varianten, weil der
exakte Slug nicht öffentlich steht. Nur stdlib. Nach Phase 0 in den Papierkorb.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# (Version, Ressource) — dokumentierte Platform-APIs, die wir brauchen.
CANDIDATES = [
    ("v1", "lessons"), ("v1", "lesson"),
    ("v1", "students"), ("v1", "student"),
    ("v1", "classes"), ("v1", "class"),
    ("v1", "student-groups"), ("v1", "studentGroups"),
]


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
    print(f"Token  POST {url}  →  {status}")
    if status != 200:
        die(f"Token-Call fehlgeschlagen ({status}):\n{body}")
    tok = json.loads(body)
    if not tok.get("access_token"):
        die(f"Kein access_token:\n{body}")
    print(f"       Bearer erhalten, expires_in={tok.get('expires_in')}s\n")
    return tok["access_token"]


def main() -> None:
    load_env()
    tenant = os.environ.get("UNTIS_TENANT_ID", "").strip()
    client = os.environ.get("UNTIS_CLIENT_ID", "").strip()
    secret = os.environ.get("UNTIS_CLIENT_SECRET", "").strip()
    token_base = os.environ.get("UNTIS_TOKEN_BASE", "https://api.webuntis.com").rstrip("/")
    api_base = os.environ.get("UNTIS_API_BASE", "https://api.webuntis.com").rstrip("/")

    if not (tenant and client and secret):
        die("UNTIS_TENANT_ID / UNTIS_CLIENT_ID / UNTIS_CLIENT_SECRET fehlen.")

    token = get_token(token_base, tenant, client, secret)
    out = Path("spike/out")
    out.mkdir(parents=True, exist_ok=True)
    hits: list[str] = []

    for ver, res in CANDIDATES:
        url = f"{api_base}/WebUntis/api/rest/extern/{ver}/{res}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        status, body = http(req)
        # 404 = Slug falsch; 400 = existiert, will Parameter; 200 = Treffer;
        # 401/403/500 "denied" = Endpunkt da, aber Berechtigung fehlt.
        tag = {200: "✓ TREFFER", 400: "~ da (braucht Parameter)"}.get(
            status, "· denied/Berechtigung" if status in (401, 403, 500) else "× 404")
        print(f"{tag:28s} {status}  {ver}/{res}")
        if status in (200, 400):
            hits.append(f"{ver}/{res} → {status}")
            snippet = body[:600].replace("\n", " ")
            print(f"     {snippet}")
            if status == 200 and body.strip():
                (out / f"extern_{res}.json").write_text(body, encoding="utf-8")
                try:
                    data = json.loads(body)
                    for path, val in sorted(structure(data).items())[:40]:
                        print(f"       {path:44s} {val}")
                except json.JSONDecodeError:
                    pass
        print()

    print("── Fazit ──")
    if hits:
        print("Erreichbare extern-Endpunkte:", ", ".join(hits))
        print("→ Diesen Satz nutzen. 400 heißt: Pflichtparameter im Body/Fehlertext"
              " ergänzen (Schuljahr/Zeitraum).")
    else:
        print("Alle extern-Endpunkte abgewiesen. Dann ist auch dieser Client nicht"
              " für die Daten-API berechtigt → Untis/Partner: OneRoster- bzw.")
        print("extern-Leserecht für den Mandanten freischalten.")


if __name__ == "__main__":
    main()
