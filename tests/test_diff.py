"""Tests für den Diff-Kern (Phase 3)."""
import unittest

from asv_webuntis.diff import diff, summarize


class TestDiff(unittest.TestCase):
    def setUp(self):
        self.asv = {("A", "Re82"), ("A", "Sp10"), ("B", "M1_11"),
                    ("C", "XKurs"), ("Z", "Re82")}
        self.ist = {("A", "Re82"), ("A", "M1_11"), ("B", "M1_11")}
        self.wu_groups = {"Re82", "Sp10", "M1_11"}
        self.wu_students = {"A", "B", "C"}

    def test_alle_kategorien_ohne_mapping(self):
        got = {(x.art, x.schueler_key, x.gruppe)
               for x in diff(self.asv, self.ist, self.wu_groups, self.wu_students)}
        self.assertIn(("FEHLT_IN_WU", "A", "Sp10"), got)          # in ASV, fehlt im Ist
        self.assertIn(("GRUPPE_UNBEKANNT", "C", "XKurs"), got)    # Gruppe ohne WU-Pendant
        self.assertIn(("SCHUELER_UNBEKANNT", "Z", "Re82"), got)  # ID nicht in WU
        self.assertIn(("ZUVIEL_IN_WU", "A", "M1_11"), got)       # im Ist, nicht in ASV
        self.assertNotIn(("FEHLT_IN_WU", "A", "Re82"), got)      # Treffer → kein Finding
        self.assertEqual(len(got), 4)

    def test_mapping_loest_gruppe_unbekannt(self):
        got = {(x.art, x.schueler_key, x.gruppe)
               for x in diff(self.asv, self.ist, self.wu_groups, self.wu_students,
                             mapping={"XKurs": "M1_11"})}
        # C/XKurs → M1_11 ist bekannt, aber (C,M1_11) fehlt im Ist → FEHLT statt UNBEKANNT
        self.assertIn(("FEHLT_IN_WU", "C", "XKurs"), got)
        self.assertNotIn(("GRUPPE_UNBEKANNT", "C", "XKurs"), got)

    def test_summarize(self):
        s = summarize(diff(self.asv, self.ist, self.wu_groups, self.wu_students))
        self.assertEqual(s["counts"]["FEHLT_IN_WU"], 1)
        self.assertEqual(s["counts"]["ZUVIEL_IN_WU"], 1)
        self.assertEqual(s["gruppe_unbekannt"], ["XKurs"])
        self.assertEqual(s["schueler_unbekannt"], ["Z"])


if __name__ == "__main__":
    unittest.main()
