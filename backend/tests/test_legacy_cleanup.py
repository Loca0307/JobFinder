import unittest
from unittest.mock import MagicMock, Mock

from api.services.legacy_cleanup import cleanup_legacy_items


class LegacyCleanupTests(unittest.TestCase):
    def setUp(self):
        self.table = MagicMock()
        self.table.scan.return_value = {
            "Items": [
                {"PK": "JOB#1", "SK": "METADATA", "item_type": "JOB"},
                {"PK": "SOURCE#jobs.ch", "SK": "METADATA", "item_type": "SOURCE"},
                {"PK": "USER#default", "SK": "JOB#1", "item_type": "JOB_INTERACTION"},
            ]
        }

    def test_dry_run_does_not_delete(self):
        result = cleanup_legacy_items(table=self.table)

        self.assertEqual(result, {"found": 2, "deleted": 0})
        self.table.batch_writer.assert_not_called()

    def test_confirm_deletes_only_legacy_items(self):
        batch = Mock()
        self.table.batch_writer.return_value.__enter__.return_value = batch

        result = cleanup_legacy_items(confirm=True, table=self.table)

        self.assertEqual(result, {"found": 2, "deleted": 2})
        deleted_keys = [call.kwargs["Key"] for call in batch.delete_item.call_args_list]
        self.assertEqual(deleted_keys, [
            {"PK": "JOB#1", "SK": "METADATA"},
            {"PK": "SOURCE#jobs.ch", "SK": "METADATA"},
        ])


if __name__ == "__main__":
    unittest.main()
