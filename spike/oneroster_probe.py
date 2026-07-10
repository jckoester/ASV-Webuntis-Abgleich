#!/usr/bin/env python3
"""Wegwerf-Spike Phase 0 — read-only. Token (Client-Credentials) holen und je
eine kleine Stichprobe aus OneRoster students / classes / enrollments lesen.

Beantwortet:
  Q1  Schülergruppenname  → in classes.title / course sichtbar?
  Q2  externe Schüler-ID  → students[].userIds / metadata (external-person-id)
  Q4  Von/Bis-Datum       → enrollments.beginDate / endDate
  Q7  echte Namen vs ASV  → classes.title-Werte

Nur stdlib, kein pip install. Nach Phase 0 in den Papierkorb. Siehe Phase-0.md.
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

RESOURCES = ("students", "classes", "enrollments")
SAMPLE = 5  # kleine Stichprobe — kein Voll-Export im Spike


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
            v = v[1:-1]  # versehentliche Anführungszeichen entfernen
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
    """Alle Feldpfade eines JSON-Baums flach ziehen (1. Listen-Element)."""
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
        hint = ""
        if "invalid_grant" in body or "invalid_client" in body:
            hint = ("\n→ Meist falsches Secret: Client-Credentials braucht das "
                    "SELBST-GENERIERTE Plattform-Passwort, NICHT das OIDC Client "
                    "Secret. Frisches Passwort z. B. via Moodle-Plattform-"
                    "Applikation (zeigt es beim Speichern einmalig an).")
        die(f"Token-Call fehlgeschlagen ({status}):\n{body}{hint}")
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
        die("UNTIS_TENANT_ID / UNTIS_CLIENT_ID / UNTIS_CLIENT_SECRET fehlen "
            "(.env aus .env.example anlegen).")

    token = get_token(token_base, tenant, client, secret)
    out = Path("spike/out")
    out.mkdir(parents=True, exist_ok=True)

    for res in RESOURCES:
        url = f"{api_base}/ims/oneroster/v1p1/{res}?limit={SAMPLE}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        status, body = http(req)
        print(f"── {res.upper()}  GET {url}  →  {status}")
        if status != 200:
            print(f"   Fehlertext (evtl. anderer Host/Pfad? → UNTIS_API_BASE "
                  f"testweise auf Schulhost ggd.webuntis.com):\n   {body[:500]}\n")
            continue
        (out / f"oneroster_{res}.json").write_text(body, encoding="utf-8")
        data = json.loads(body)
        # OneRoster-Envelope: {"students":[...]} bzw. erste Liste im Objekt
        items = data.get(res) if isinstance(data, dict) else data
        if items is None and isinstance(data, dict):
            items = next((v for v in data.values() if isinstance(v, list)), None)
        n = len(items) if isinstance(items, list) else "?"
        print(f"   gespeichert: {out/f'oneroster_{res}.json'}  (Stichprobe: {n})")
        for path, val in sorted(structure(items[0] if items else data).items()):
            print(f"      {path:42s} {val}")
        print()

    print("Jetzt Q1–Q7 in Phase-0-Ergebnis.md eintragen (pseudonymisiert!):")
    print("  Q1 Gruppenname   → classes: welches Feld trägt die Schülergruppe?")
    print("  Q2 externe ID    → students: Feld mit external-person-id / sourcedId")
    print("  Q4 Datum         → enrollments: beginDate / endDate vorhanden?")
    print("  Q7 Namen vs ASV  → classes.title-Werte mit ASV-Bezeichnungen vergleichen")


if __name__ == "__main__":
    main()
