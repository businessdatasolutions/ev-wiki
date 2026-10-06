"""Offline tests voor het koppelen van titels aan modellen in de verzamelaar.

    uv run --no-project --with-requirements .claude/skills/youtube-transcript-skill/requirements.txt \\
        python -m unittest onderzoek/test_verzamelaar.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verzamelaar as v  # noqa: E402


def m(sleutel: str) -> dict:
    merk, model = sleutel.split("/")
    return {"pad": f"/deals/{sleutel}", "sleutel": sleutel, "merk_woorden": merk.split("-"),
            "model_woorden": model.split("-"), "naam": f"{merk} {model}"}


# Een deel van de sitemap van plinkie.nl op 06-10-2026, met de dubbele paden erin.
MODELLEN = [m(s) for s in (
    "dongfeng/box", "kia/ev2", "kia/ev3", "kia/ev4", "kia/ev4-fastback", "leapmotor/t03",
    "citroen/e-c3", "citroen/e-c3-aircross", "renault/4", "renault/4-e-tech", "renault/5",
    "renault/5-e-tech", "volkswagen/id-polo", "volkswagen/id-3", "fiat/grande-panda",
    "fiat/grande-panda-e", "hyundai/ioniq-5", "hyundai/ioniq-5-n", "alfa-romeo/junior",
    "audi/e-tron", "audi/q4-e-tron", "audi/e-tron-gt",
    "mercedes-benz/c-klasse-limousine", "mercedes-benz/glc", "hyundai/kona-electric", "toyota/c-hr-plus",
)]


class Koppelen(unittest.TestCase):
    def t(self, titel):
        return sorted(v.modellen_in(titel, MODELLEN))

    def test_echte_titels(self):
        # Titels zoals de verkenning ze op 06-10-2026 vond
        self.assertEqual(self.t("Test: Dongfeng Box - Bizar veel auto voor je geld"), ["dongfeng/box"])
        self.assertEqual(self.t("Grote actieradius en goed rijgedrag voor nieuwe Kia EV2"), ["kia/ev2"])
        self.assertEqual(self.t("Can the Volkswagen ID Polo take on the successful Renault 5?"),
                         ["renault/5", "volkswagen/id-polo"])

    def test_diakriet_en_streepje(self):
        self.assertEqual(self.t("Citroën ë-C3 getest"), ["citroen/e-c3"])
        self.assertEqual(self.t("Citroen e-C3 Aircross review"), ["citroen/e-c3-aircross"])
        self.assertEqual(self.t("VW ID.3 in de winter"), ["volkswagen/id-3"])

    def test_langste_treffer_wint(self):
        self.assertEqual(self.t("Renault 4 E-Tech: retro met stroom"), ["renault/4-e-tech"])
        self.assertEqual(self.t("Hyundai Ioniq 5 N op het circuit"), ["hyundai/ioniq-5-n"])

    def test_model_binnen_een_ander_model(self):
        # Verkenning 06-10-2026: "audi/e-tron" kwam bij elke Audi Q4 e-tron mee
        self.assertEqual(self.t("Audi Q4 e-tron Sportback getest"), ["audi/q4-e-tron"])
        self.assertEqual(self.t("Audi e-tron GT tegen Porsche Taycan"), ["audi/e-tron-gt"])
        self.assertEqual(self.t("De oude Audi e-tron als occasion"), ["audi/e-tron"])

    def test_merk_is_verplicht(self):
        self.assertEqual(self.t("De box van de Wegenwacht"), [])
        self.assertEqual(self.t("Junior (19) heeft een unieke verzameling"), [])

    def test_model_van_een_teken_alleen_na_het_merk(self):
        self.assertEqual(self.t("Renault Austral 4x4 met 5 jaar garantie"), [])
        self.assertEqual(self.t("Renault 5 tegen Renault 4"), ["renault/4", "renault/5"])

    def test_meerdere_modellen_in_een_vergelijking(self):
        self.assertEqual(self.t("Kia EV3 vs Kia EV2: welke kies je?"), ["kia/ev2", "kia/ev3"])

    def test_merk_van_twee_woorden(self):
        self.assertEqual(self.t("Alfa Romeo Junior Elettrica review"), ["alfa-romeo/junior"])


class AnwbTitels(unittest.TestCase):
    """Titels van ANWB-reviews (06-10-2026): korter merk, en zonder de algemene woorden van Plinkie."""
    def t(self, titel):
        return sorted(v.modellen_in(titel, MODELLEN))

    def test_mercedes_is_mercedes_benz(self):
        self.assertEqual(self.t("Mercedes C-Klasse VI (W520)"), ["mercedes-benz/c-klasse-limousine"])
        self.assertEqual(self.t("Mercedes-Benz GLC"), ["mercedes-benz/glc"])

    def test_algemeen_achtervoegsel_mag_ontbreken(self):
        self.assertEqual(self.t("Hyundai Kona II"), ["hyundai/kona-electric"])

    def test_plus_is_een_woord(self):
        self.assertEqual(self.t("Toyota C-Hr+ I"), ["toyota/c-hr-plus"])

    def test_preciezere_treffer_gaat_voor(self):
        # Staat het hele model erin, dan geen tweede ronde voor dat merk
        self.assertEqual(self.t("Audi Q4 e-tron"), ["audi/q4-e-tron"])


class Herkansing(unittest.TestCase):
    def test_mislukt_krijgt_herkansing_tot_max(self):
        self.assertFalse(v.klaar_mee(None))
        self.assertFalse(v.klaar_mee({"status": "mislukt", "pogingen": 1}))
        self.assertTrue(v.klaar_mee({"status": "mislukt", "pogingen": v.MAX_POGINGEN}))
        self.assertTrue(v.klaar_mee({"status": "opgehaald"}))
        self.assertTrue(v.klaar_mee({"status": "overgeslagen"}))


class Slug(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(v.slugify("Test: Dongfeng Box - Bizar veel auto!"), "test-dongfeng-box-bizar-veel-auto")


if __name__ == "__main__":
    unittest.main()
