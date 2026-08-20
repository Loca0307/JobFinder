import json
import tempfile
import unittest
from pathlib import Path

from api.scrapers.ats.targets import (
    GreenhouseTarget,
    LeverTarget,
    load_company_target_catalog,
)


def write_catalog(path: Path, targets: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"targets": targets}), encoding="utf-8")


def greenhouse_target(**updates: object) -> dict[str, object]:
    target: dict[str, object] = {
        "id": "example-greenhouse",
        "company_name": "Example Greenhouse AG",
        "careers_url": "https://example.test/careers",
        "ats": "greenhouse",
        "board_token": "example",
    }
    target.update(updates)
    return target


def lever_target(**updates: object) -> dict[str, object]:
    target: dict[str, object] = {
        "id": "example-lever",
        "company_name": "Example Lever AG",
        "careers_url": "https://example.test/jobs",
        "ats": "lever",
        "site": "example",
        "region": "eu",
    }
    target.update(updates)
    return target


class CompanyTargetCatalogTests(unittest.TestCase):
    def test_catalog_loads_empty_and_supported_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            empty_path = Path(directory) / "empty.json"
            write_catalog(empty_path, [])
            self.assertEqual(load_company_target_catalog(empty_path).targets, [])

            path = Path(directory) / "targets.json"
            write_catalog(path, [greenhouse_target(), lever_target()])
            catalog = load_company_target_catalog(path)

        self.assertIsInstance(catalog.targets[0], GreenhouseTarget)
        self.assertIsInstance(catalog.targets[1], LeverTarget)
        self.assertEqual(
            [target.source_name for target in catalog.targets],
            ["company:example-greenhouse", "company:example-lever"],
        )

    def test_catalog_rejects_invalid_targets(self):
        invalid_catalogs = (
            [greenhouse_target(), greenhouse_target(company_name="Duplicate")],
            [greenhouse_target(id="Bad ID")],
            [greenhouse_target(careers_url="not-a-url")],
            [greenhouse_target(board_token="bad/token")],
            [lever_target(site="bad/site")],
            [lever_target(region="us")],
            [greenhouse_target(ats="workday")],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            for targets in invalid_catalogs:
                with self.subTest(targets=targets):
                    write_catalog(path, targets)
                    with self.assertRaisesRegex(ValueError, "company target|Duplicate"):
                        load_company_target_catalog(path)

    def test_catalog_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"

            with self.assertRaisesRegex(ValueError, "Cannot read"):
                load_company_target_catalog(path)


if __name__ == "__main__":
    unittest.main()
