"""Tests für den lesbaren Report (Phase 4)."""
import unittest

from asv_webuntis.diff import Finding
from asv_webuntis.report import render


class TestReport(unittest.TestCase):
    def test_render_gruppiert(self):
        findings = [
            Finding("FEHLT_IN_WU", "k1", "Re11"),
            Finding("FEHLT_IN_WU", "k5", "Re11"),
            Finding("ZUVIEL_IN_WU", "k2", "M1_11"),
            Finding("ZUVIEL_IN_WU", "kx", "ET_8"),   # kx nur in WebUntis
            Finding("GRUPPE_UNBEKANNT", "k9", "F61"),
            Finding("GRUPPE_NUR_IN_WU", "k3", "PHANTOM"),
            Finding("SCHUELER_UNBEKANNT", "k4", "Sp10"),
        ]
        names = {"k1": "Max M", "k5": "Amy A", "k2": "Anna B",
                 "k3": "Peter T", "k4": "Zoe Z", "kx": "WU Only"}
        asv_ids = {"k1", "k5", "k2", "k3", "k4"}      # kx NICHT im ASV-Export
        txt = render(findings, {"Re11": ["REL_11"]}, names, {"PHANTOM": 5},
                     "2025-11-17", asv_ids=asv_ids)
        self.assertIn("Re11  →  WebUntis: REL_11", txt)
        self.assertIn("+  Amy A", txt)        # nach Name sortiert (vor Max)
        self.assertIn("Bis-Datum", txt)
        self.assertIn("−  Anna B", txt)       # k2 in ASV → normale ZUVIEL
        self.assertIn("nur in WebUntis", txt)
        self.assertIn("WU Only  →  ET_8", txt)  # kx separat ausgewiesen
        self.assertIn("F61", txt)             # GRUPPE_UNBEKANNT
        self.assertIn("PHANTOM  (n=5)", txt)
        self.assertIn("Zoe Z", txt)           # SCHUELER_UNBEKANNT mit Name
        self.assertLess(txt.index("Amy A"), txt.index("Max M"))

    def test_render_leer(self):
        self.assertIn("(keine)", render([], {}, {}, {}, "2025-11-17"))


if __name__ == "__main__":
    unittest.main()
