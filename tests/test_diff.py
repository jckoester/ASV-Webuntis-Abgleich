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

    def test_eins_zu_viele_jahrgansuebergreifend(self):
        # ein ASV-Code → zwei WU-Gruppen; Schüler in EINER davon = Treffer
        asv = {("A", "BKlk"), ("B", "BKlk")}
        ist = {("A", "BK_11"), ("B", "BK_12")}
        findings = diff(asv, ist, {"BK_11", "BK_12"}, {"A", "B"},
                        mapping={"BKlk": ["BK_11", "BK_12"]})
        self.assertEqual(findings, [])  # beide gedeckt, kein FEHLT/ZUVIEL
        # ohne die zweite Zielgruppe wäre B FEHLT_IN_WU:
        f2 = diff(asv, ist, {"BK_11", "BK_12"}, {"A", "B"}, mapping={"BKlk": ["BK_11"]})
        self.assertIn(("FEHLT_IN_WU", "B"), {(x.art, x.schueler_key) for x in f2})

    def test_gruppe_nur_in_wu_phantom(self):
        # WU-Gruppe, auf die kein ASV zeigt → GRUPPE_NUR_IN_WU (nicht ZUVIEL)
        got = {(x.art, x.gruppe) for x in diff(
            {("A", "G1")}, {("A", "G1"), ("X", "PHANTOM")},
            {"G1", "PHANTOM"}, {"A", "X"})}
        self.assertIn(("GRUPPE_NUR_IN_WU", "PHANTOM"), got)
        self.assertNotIn(("ZUVIEL_IN_WU", "PHANTOM"), got)

    def test_merge_mappings_manuell_gewinnt(self):
        from asv_webuntis.diff import merge_mappings
        auto = {"X": ["autoX"], "Y": ["autoY"]}
        manual = {"X": ["manuellX"], "Z": ["-"]}
        m = merge_mappings(auto, manual)
        self.assertEqual(m["X"], ["manuellX"])  # manuell überschreibt auto
        self.assertEqual(m["Y"], ["autoY"])
        self.assertEqual(m["Z"], ["-"])

    def test_ignore_sentinel_kein_befund(self):
        # POOL_X bewusst als "kein WU-Pendant" markiert → kein GRUPPE_UNBEKANNT
        f = diff({("A", "POOL_X")}, set(), set(), {"A"}, mapping={"POOL_X": ["-"]})
        self.assertEqual(f, [])

    def test_summarize(self):
        s = summarize(diff(self.asv, self.ist, self.wu_groups, self.wu_students))
        self.assertEqual(s["counts"]["FEHLT_IN_WU"], 1)
        self.assertEqual(s["counts"]["ZUVIEL_IN_WU"], 1)
        self.assertEqual(s["gruppe_unbekannt"], ["XKurs"])
        self.assertEqual(s["schueler_unbekannt"], ["Z"])


if __name__ == "__main__":
    unittest.main()
