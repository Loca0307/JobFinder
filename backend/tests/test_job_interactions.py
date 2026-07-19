import unittest
from unittest.mock import Mock, patch

from api.data.schemas import JobInteractionWrite, JobRead
from api.services.job_interactions import save_job_interaction


def interaction(starred=False, applied=False):
    return JobInteractionWrite(
        job=JobRead(
            id="jobs.ch#123",
            title="Python Developer",
            source_website="jobs.ch",
            source_url="https://example.test/job",
        ),
        starred=starred,
        applied=applied,
    )


class JobInteractionTests(unittest.TestCase):
    @patch("api.services.job_interactions.get_jobs_table")
    def test_starring_stores_full_job_snapshot(self, get_table):
        table = Mock()
        table.get_item.return_value = {}
        get_table.return_value = table

        saved = save_job_interaction("jobs.ch#123", interaction(starred=True))

        item = table.put_item.call_args.kwargs["Item"]
        self.assertEqual(item["PK"], "USER#default")
        self.assertEqual(item["SK"], "JOB#jobs.ch#123")
        self.assertEqual(item["job"]["title"], "Python Developer")
        self.assertTrue(saved.starred)

    @patch("api.services.job_interactions.get_jobs_table")
    def test_unstar_keeps_applied_job(self, get_table):
        table = Mock()
        table.get_item.return_value = {
            "Item": {
                "created_at": "2026-07-19T10:00:00+00:00",
                "applied_at": "2026-07-19T11:00:00+00:00",
                "applied": True,
            }
        }
        get_table.return_value = table

        saved = save_job_interaction("jobs.ch#123", interaction())

        table.delete_item.assert_not_called()
        self.assertFalse(saved.starred)
        self.assertTrue(saved.applied)
        self.assertEqual(saved.applied_at.isoformat(), "2026-07-19T11:00:00+00:00")

    @patch("api.services.job_interactions.get_jobs_table")
    def test_empty_interaction_is_deleted(self, get_table):
        table = Mock()
        table.get_item.return_value = {}
        get_table.return_value = table

        saved = save_job_interaction("jobs.ch#123", interaction())

        self.assertIsNone(saved)
        table.delete_item.assert_called_once()
        table.put_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
