"""Testfälle Phase 1 — an echten (pseudonymisierten) Musterzeilen belegt.
Reines stdlib (unittest): `python3 -m unittest discover -s tests -t .`
"""
import os
import tempfile
import unittest

from asv_webuntis.parser import (
    COL_GROUPS,
    COL_KEY,
    Record,
    classify_entry,
    dedupe,
    parse_export,
    split_entries,
)


class TestSplitEntries(unittest.TestCase):
    def test_mehrere_eintraege(self):
        s = ("SPA/Sp10/Spanisch Schröder, MUS/10C/1/Musik Brost, "
             "SPO-W/Sw12/Sport weiblich Scholl, F/F11/Französisch Schröder, "
             "REV/Re11/Evang.Religionslehre Müller-Lüdenscheidt")
        self.assertEqual(len(split_entries(s)), 5)

    def test_erster_eintrag_ohne_fuehrendes_komma(self):
        self.assertEqual(split_entries("SPA/Sp10/Spanisch Schröder"),
                         ["SPA/Sp10/Spanisch Schröder"])

    def test_komma_im_klartext_trennt_nicht(self):
        s = "GK/Gk11/Gemeinschaftskunde, Wirtschaft Kunz, MA/Ma10/Mathematik Kunz"
        self.assertEqual(
            split_entries(s),
            ["GK/Gk11/Gemeinschaftskunde, Wirtschaft Kunz", "MA/Ma10/Mathematik Kunz"])

    def test_kleinbuchstaben_kuerzel(self):
        s = "NwT/Nw10/Naturw. u. Technik Scholl, BnT/Bn10/Bio-Nawi-Technik Kunz"
        self.assertEqual(len(split_entries(s)), 2)

    def test_kursstufe_komma_in_klammer_trennt_korrekt(self):
        # Komma in [3,00] darf NICHT trennen; Grenze vor D[..] muss greifen.
        s = "REV/Re82/1/Religion X, D[3,00]_1.2_2/Deutsch Y, POOL_8Na/8D/2/Pool Z"
        self.assertEqual(len(split_entries(s)), 3)

    @unittest.expectedFailure  # mehrwortige AG-Namen kleben mid-list; AGs sind eh out of scope
    def test_mehrwort_ag_klebt(self):
        s = "REV/Re11/Religion X, Make it, sell it/AG1/Werken Y"
        self.assertEqual(len(split_entries(s)), 2)

    def test_leer(self):
        self.assertEqual(split_entries(""), [])


class TestClassifyEntry(unittest.TestCase):
    """Die vier realen Musterzeilen (Lehrernamen → 'X') plus Kanten."""

    def test_sek1_mit_schiene(self):
        self.assertEqual(classify_entry("REV/Re82/1/Evang.Religionslehre X"),
                         ("Re82", "REV", "sek1", "1/Evang.Religionslehre X"))

    def test_sek1_ohne_schiene(self):
        self.assertEqual(classify_entry("SPA/Sp10/Spanisch X"),
                         ("Sp10", "SPA", "sek1", "Spanisch X"))

    def test_ganze_klasse_verworfen(self):
        self.assertIsNone(classify_entry("BIO_1/8D/1/Biologie X"))

    def test_kursstufe_gruppe_ist_code_fach_ist_praefix(self):
        self.assertEqual(classify_entry("D[3,00]_1.2_2/Deutsch X"),
                         ("D[3,00]_1.2_2", "D", "kursstufe", "Deutsch X"))

    def test_pool_gruppe_ist_field0(self):
        self.assertEqual(classify_entry("POOL_8Na/8D/2/Poolstunden X"),
                         ("POOL_8Na", "POOL_8Na", "pool", "2/Poolstunden X"))

    def test_slash_im_klartext_bleibt_in_rest(self):
        self.assertEqual(
            classify_entry("WBS/Wbs10/Wirtschaft / Berufs- u. Studienorientierung X"),
            ("Wbs10", "WBS", "sek1", "Wirtschaft / Berufs- u. Studienorientierung X"))

    def test_ag_einwort_verworfen(self):
        self.assertIsNone(classify_entry("Band/Big Band X"))

    def test_ag_mehrwort_kopf_verworfen(self):
        self.assertIsNone(classify_entry("Make it, sell it/AG1/Werken X"))

    def test_schrott_ohne_slash(self):
        self.assertIsNone(classify_entry("Kaputt"))


class TestParseExport(unittest.TestCase):
    def test_gegen_synthetisches_csv(self):
        content = (
            f"{COL_KEY};{COL_GROUPS}\n"
            "GUID-1;REV/Re82/1/Religion X, BIO_1/8D/1/Biologie X, Band/Big Band X\n"
            "GUID-2;D[3,00]_1.2_2/Deutsch X, POOL_8Na/8D/2/Pool X\n"
        )
        with tempfile.NamedTemporaryFile(
                "w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            f.write(content)
            path = f.name
        try:
            recs = parse_export(path)
        finally:
            os.unlink(path)
        got = sorted((r.schueler_key, r.gruppe, r.art) for r in recs)
        self.assertEqual(got, [
            ("GUID-1", "Re82", "sek1"),
            ("GUID-2", "D[3,00]_1.2_2", "kursstufe"),
            ("GUID-2", "POOL_8Na", "pool"),
        ])

    def test_dedupe(self):
        r = Record("G1", "Re82", "REV", "sek1")
        self.assertEqual(dedupe([r, r]), [r])

    def test_fehlende_spalte_meldet_klar(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            f.write("a;b\n1;2\n")
            path = f.name
        try:
            with self.assertRaises(ValueError):
                parse_export(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
