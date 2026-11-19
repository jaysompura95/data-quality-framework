import io
import unittest
from unittest.mock import MagicMock, patch

from dq.adapters import ClickHouseAdapter, UnsafeQueryError


class ClickHouseAdapterTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_tables(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"accounts\ncontacts\norganisations\n"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        adapter = ClickHouseAdapter(url="http://localhost:8123", database="analytics")
        tables = adapter.tables()

        self.assertEqual(tables, ["accounts", "contacts", "organisations"])
        self.assertTrue(mock_urlopen.called)

    @patch("urllib.request.urlopen")
    def test_columns(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"organisation_id\naccount_id\ncontact_id\n"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        adapter = ClickHouseAdapter(url="http://localhost:8123", database="analytics")
        cols = adapter.columns("accounts")

        self.assertEqual(cols, ["organisation_id", "account_id", "contact_id"])

    @patch("urllib.request.urlopen")
    def test_count_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"0\n"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        adapter = ClickHouseAdapter(url="http://localhost:8123", database="analytics")
        valid_query = "SELECT COUNT(*) FROM (SELECT 1 FROM contacts WHERE organisation_id IS NULL) AS q"
        count = adapter.count(valid_query)

        self.assertEqual(count, 0)

    def test_count_blocks_unsafe_raw_row_query(self):
        adapter = ClickHouseAdapter(url="http://localhost:8123", database="analytics")
        with self.assertRaises(UnsafeQueryError):
            adapter.count("SELECT * FROM contacts")

    @patch("urllib.request.urlopen")
    def test_count_rejects_non_integer_output(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"NOT_A_NUMBER\n"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        adapter = ClickHouseAdapter(url="http://localhost:8123", database="analytics")
        valid_query = "SELECT COUNT(*) FROM (SELECT 1 FROM contacts) AS q"
        with self.assertRaises((UnsafeQueryError, ValueError)):
            adapter.count(valid_query)


if __name__ == "__main__":
    unittest.main()
