"""Tests für den Mitglieder-Überlappungs-Mapper (Phase 3)."""
import unittest

from asv_webuntis.mapper import members, propose


class TestMapper(unittest.TestCase):
    def setUp(self):
        # asvG1 = {A,B,C}, asvG2 = {A,B}
        self.asv = {("A", "asvG1"), ("B", "asvG1"), ("C", "asvG1"),
                    ("A", "asvG2"), ("B", "asvG2")}
        # wuX = {A,B,C} (identisch zu asvG1), wuY = {A,B,D}
        self.ist = {("A", "wuX"), ("B", "wuX"), ("C", "wuX"),
                    ("A", "wuY"), ("B", "wuY"), ("D", "wuY")}

    def test_members(self):
        self.assertEqual(members(self.asv)["asvG1"], {"A", "B", "C"})

    def test_perfekter_match(self):
        props = {p.asv_gruppe: p for p in propose(self.asv, self.ist)}
        self.assertEqual(props["asvG1"].wu_gruppen, ("wuX",))
        self.assertEqual(props["asvG1"].abdeckung, 1.0)

    def test_teilmenge_volle_abdeckung(self):
        # asvG2={A,B} ⊂ wuX{A,B,C} → ein Ziel, Abdeckung 1.0
        p = {p.asv_gruppe: p for p in propose(self.asv, self.ist)}["asvG2"]
        self.assertEqual(p.abdeckung, 1.0)
        self.assertEqual(len(p.wu_gruppen), 1)

    def test_jahrgansuebergreifend_zwei_ziele(self):
        # ein ASV-Code, dessen Schüler auf zwei WU-Gruppen aufgeteilt sind
        asv = {("A", "K"), ("B", "K"), ("C", "K"), ("D", "K")}
        ist = {("A", "wu11"), ("B", "wu11"), ("C", "wu12"), ("D", "wu12")}
        p = propose(asv, ist)[0]
        self.assertEqual(set(p.wu_gruppen), {"wu11", "wu12"})
        self.assertEqual(p.abdeckung, 1.0)

    def test_keine_ueberlappung(self):
        self.assertEqual(propose({("Z", "einsam")}, self.ist), [])

    def test_expand_duplicates(self):
        from asv_webuntis.mapper import expand_duplicates
        # K1 und K2 haben identische Mitglieder → Duplikat, beide ins Mapping
        asv = {("A", "G"), ("B", "G")}
        ist = {("A", "K1"), ("B", "K1"), ("A", "K2"), ("B", "K2")}
        p = expand_duplicates(propose(asv, ist), ist)[0]
        self.assertEqual(set(p.wu_gruppen), {"K1", "K2"})


if __name__ == "__main__":
    unittest.main()
