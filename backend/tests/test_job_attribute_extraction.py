import unittest

from api.services.job_attribute_extraction import (
    extract_remote_type,
    extract_required_languages,
    extract_seniority,
    normalize_structured_remote_type,
)

class JobAttributeExtractionTests(unittest.TestCase):
    # Description seniority test
    def test_extracts_senior_from_description(self):
        description = "The company is currently seeking a dynamic Senior Process Engineer."

        self.assertEqual(extract_seniority("Process Engineer", description), "senior")
    # Title seniority test
    def test_title_seniority_takes_priority(self):
        self.assertEqual(
            extract_seniority("Junior Developer", "You will work with senior engineers."),
            "junior",
        )
    # Multiple language names test
    def test_extracts_and_deduplicates_multilingual_language_names(self):
        self.assertEqual(
            extract_required_languages(
                "German-speaking Consultant",
                "Fluent English and Deutsch are required. Français is beneficial.",
            ),
            ["English", "German", "French"],
        )
    
    def test_returns_empty_values_when_no_attributes_are_mentioned(self):
        self.assertIsNone(extract_seniority("Process Engineer", "Build plants."))
        self.assertIsNone(extract_remote_type("Process Engineer", "Build plants."))
        self.assertEqual(
            extract_required_languages("Process Engineer", "Build plants."), []
        )

    def test_extracts_hybrid_before_generic_remote_wording(self):
        self.assertEqual(
            extract_remote_type(
                "Software Engineer", "This is a hybrid role with partially remote work."
            ),
            "hybrid",
        )

    def test_extracts_remote_from_title(self):
        self.assertEqual(
            extract_remote_type("Remote Backend Engineer", "Join our Zurich team."),
            "remote",
        )

    def test_explicit_no_remote_maps_to_on_site(self):
        self.assertEqual(
            extract_remote_type(
                "Process Engineer", "Presence required; remote work is not possible."
            ),
            "on_site",
        )

    def test_extracts_real_jobs_ch_homeoffice_phrases_as_hybrid(self):
        examples = (
            "Homeoffice-Option (1 Tag pro Woche)",
            "Ein flexibles Arbeitsmodell inklusive Homeoffice-Möglichkeit",
            "Flexible working hours and the possibility for home office",
            "A healthy mix of presence work and homeoffice",
        )

        for description in examples:
            with self.subTest(description=description):
                self.assertEqual(
                    extract_remote_type("Engineer", description), "hybrid"
                )

    def test_does_not_treat_technical_hybrid_or_role_name_as_remote_work(self):
        self.assertIsNone(
            extract_remote_type(
                "Home Office Construction Engineer",
                "We design on-premise, cloud and hybrid solutions for customers.",
            )
        )

    def test_normalizes_structured_jobs_ch_remote_type(self):
        self.assertEqual(
            normalize_structured_remote_type("Working from home"), "remote"
        )
        self.assertEqual(normalize_structured_remote_type("TELECOMMUTE"), "remote")


if __name__ == "__main__":
    unittest.main()
