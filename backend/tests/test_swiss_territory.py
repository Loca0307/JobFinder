import unittest

from api.services.swiss_territory import (
    country_code_from_evidence,
    infer_swiss_country_code,
    normalize_country_code,
)


class SwissTerritoryTests(unittest.TestCase):
    def test_swiss_location_evidence_is_recognized(self):
        locations = (
            "Zürich",
            "Geneva",
            "Remote - Switzerland",
            "Lausanne, Suisse",
            "Example Street 1, 8000, Zürich, CH",
            "Zurich, London",
        )

        for location in locations:
            with self.subTest(location=location):
                self.assertEqual(infer_swiss_country_code(location), "CH")

    def test_unknown_or_foreign_location_text_is_not_guessed(self):
        locations = (
            None,
            "",
            "London",
            "Busan",
            "Shanghai",
            "Remote",
            "Remote - Europe",
        )

        for location in locations:
            with self.subTest(location=location):
                self.assertIsNone(infer_swiss_country_code(location))

    def test_structured_country_takes_precedence_over_location_text(self):
        self.assertEqual(
            country_code_from_evidence("Zürich", structured_country="GB"),
            "GB",
        )
        self.assertIsNone(
            country_code_from_evidence(
                "Zürich",
                structured_country="United Kingdom",
            )
        )

    def test_structured_swiss_country_values_are_normalized(self):
        for value in ("CH", "ch", "CHE", "Switzerland", "Schweiz"):
            with self.subTest(value=value):
                self.assertEqual(normalize_country_code(value), "CH")


if __name__ == "__main__":
    unittest.main()
