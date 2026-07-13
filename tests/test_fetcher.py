"""Tests für die reine Fetcher-Logik (ohne API): Flatten + Stichtag.
Fixture bildet die in Phase 0 verifizierte /lesson-Struktur nach.
"""
import datetime
import unittest

from asv_webuntis.fetcher import (
    all_students,
    all_studentgroups,
    ist_at,
    lessons_to_ist,
    week_range,
)

RAW = {
    "lessons": [
        {  # normale Schülergruppe mit zwei Schülern, B tritt später bei
            "id": 1, "start": "2025-09-15", "end": "2026-07-29",
            "studentgroups": [{"shortName": "M1_11"}],
            "students": [
                {"externKey": "A", "assignments": [
                    {"start": "2025-09-15", "end": "2026-07-29"}]},
                {"externKey": "B", "assignments": [
                    {"start": "2026-02-01", "end": "2026-07-29"}]},
            ],
        },
        {  # ganze Klasse: keine studentgroups → muss übersprungen werden
            "id": 2, "start": "2025-09-15", "end": "2026-07-29",
            "classes": [{"shortName": "8D"}], "studentgroups": [],
            "students": [{"externKey": "C", "assignments": [
                {"start": "2025-09-15", "end": "2026-07-29"}]}],
        },
        {  # ohne assignments → offene Mitgliedschaft (von/bis leer)
            "id": 3, "studentgroups": [{"shortName": "Re82"}],
            "students": [{"externKey": "A", "assignments": []}],
        },
    ]
}


class TestLessonsToIst(unittest.TestCase):
    def setUp(self):
        self.ist = lessons_to_ist(RAW)

    def test_ganze_klasse_uebersprungen(self):
        self.assertNotIn("C", {r.extern_key for r in self.ist})

    def test_records_und_felder(self):
        got = sorted((r.extern_key, r.studentgroup, r.von, r.bis) for r in self.ist)
        self.assertEqual(got, [
            ("A", "M1_11", "2025-09-15", "2026-07-29"),
            ("A", "Re82", "", ""),
            ("B", "M1_11", "2026-02-01", "2026-07-29"),
        ])

    def test_leer(self):
        self.assertEqual(lessons_to_ist({}), [])


class TestIstAt(unittest.TestCase):
    def setUp(self):
        self.ist = lessons_to_ist(RAW)

    def test_vor_b_eintritt(self):
        # B ist am 15.01. noch nicht dabei; A überall (Re82 offen).
        self.assertEqual(ist_at(self.ist, "2026-01-15"),
                         {("A", "M1_11"), ("A", "Re82")})

    def test_nach_b_eintritt(self):
        self.assertEqual(ist_at(self.ist, "2026-03-01"),
                         {("A", "M1_11"), ("A", "Re82"), ("B", "M1_11")})

    def test_offene_mitgliedschaft_immer_aktiv(self):
        self.assertIn(("A", "Re82"), ist_at(self.ist, "2000-01-01"))


class TestKnownSets(unittest.TestCase):
    def test_all_studentgroups(self):
        self.assertEqual(all_studentgroups(RAW), {"M1_11", "Re82"})

    def test_all_students(self):  # inkl. C aus der ganze-Klasse-Lesson
        self.assertEqual(all_students(RAW), {"A", "B", "C"})


class TestWeekRange(unittest.TestCase):
    def test_liefert_montag_bis_freitag(self):
        start, end = week_range("2026-06-17")
        self.assertEqual(datetime.date.fromisoformat(start).weekday(), 0)  # Mo
        self.assertEqual(datetime.date.fromisoformat(end).weekday(), 4)    # Fr
        self.assertEqual(
            (datetime.date.fromisoformat(end)
             - datetime.date.fromisoformat(start)).days, 4)
        self.assertLessEqual(start, "2026-06-17")


if __name__ == "__main__":
    unittest.main()
