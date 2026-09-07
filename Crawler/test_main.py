import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from main import (CrawlError, collect_week, convert_rows, fetch_rows,
                  main, menu_count, write_json)


def row(**changes):
    value = {"camp": "1", "mCd": "20", "date": "2026.09.07",
             "rest": "참슬기식당(310관 B4층)", "course": "중식(특식)",
             "time": "11:30~13:30", "price": "5,500 원",
             "menuDetail": "<일품>쌀밥,국,김치"}
    value.update(changes)
    return value


class CrawlerTests(unittest.TestCase):
    def convert(self, rows):
        return convert_rows(rows, "1", "20", "2026.09.07")

    def test_swift_dto(self):
        result = self.convert([row()])
        self.assertEqual(result["참슬기식당(310관 B4층)"]["중식(특식)"],
                         {"time": "11:30~13:30", "price": "5,500 원",
                          "menu": "쌀밥|국|김치"})

    def test_davinci_name_compatible_with_client(self):
        result = self.convert([row(rest="(안성)라면")])
        self.assertIn("(다빈치)라면", result)

    def test_unpublished_menu_is_skipped(self):
        self.assertEqual(self.convert([row(menuDetail=None), row(menuDetail="")]), {})

    def test_malformed_menu_is_not_empty_success(self):
        value = row()
        del value["menuDetail"]
        with self.assertRaises(CrawlError):
            self.convert([value])

    def test_wrong_campus_meal_or_date_rejected(self):
        for change in ({"camp": "2"}, {"mCd": "10"}, {"date": "2024.01.01"}):
            with self.subTest(change=change), self.assertRaises(CrawlError):
                self.convert([row(**change)])

    def test_conflicting_duplicate_does_not_silently_overwrite(self):
        with self.assertRaises(CrawlError):
            self.convert([row(), row(menuDetail="다른메뉴")])

    def test_post_is_json(self):
        session = Mock()
        response = session.post.return_value
        response.status_code = 200
        response.json.return_value = {"isEmpty": "Y", "list": []}
        self.assertEqual(fetch_rows(session, "1", "20", 0), [])
        self.assertEqual(session.post.call_args.kwargs["json"],
                         {"tabs": "1", "tabs2": "20", "daily": 0})

    def test_html_and_missing_list_fail(self):
        session = Mock()
        response = session.post.return_value
        response.status_code = 200
        response.json.side_effect = ValueError("HTML")
        with self.assertRaises(CrawlError):
            fetch_rows(session, "1", "20", 0)
        response.json.side_effect = None
        response.json.return_value = {"error": "denied"}
        with self.assertRaises(CrawlError):
            fetch_rows(session, "1", "20", 0)

    @patch("main.time.sleep")
    @patch("main.fetch_rows", return_value=[])
    def test_wholly_empty_crawl_rejected(self, fetch, sleep):
        with self.assertRaises(CrawlError):
            collect_week(Mock())
        self.assertEqual(fetch.call_count, 42)

    @patch("main.collect_week", side_effect=CrawlError("request failed"))
    @patch("main.upload_to_firestore")
    def test_failed_crawl_preserves_file_and_never_uploads(self, upload, collect):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dto.json"
            path.write_text('{"old":true}')
            with self.assertRaises(CrawlError):
                main(["--output", str(path)])
            self.assertEqual(path.read_text(), '{"old":true}')
            upload.assert_not_called()

    def test_written_json_roundtrip(self):
        dto = {"0": {"2026.09.07": {"1": self.convert([row()])}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dto.json"
            write_json(dto, path)
            self.assertEqual(json.loads(path.read_text()), dto)
            self.assertEqual(menu_count(dto), 1)


if __name__ == "__main__":
    unittest.main()
