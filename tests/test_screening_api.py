import sys
import unittest
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from fastapi.exceptions import RequestValidationError  # noqa: E402
from main import app  # noqa: E402
from screening_api import ScreeningRequest, screen_case  # noqa: E402


class ScreeningApiTests(unittest.TestCase):
    def test_returns_only_five_enabled_codes_and_keeps_unknowns(self):
        request = ScreeningRequest(
            application_date=date(2026, 11, 15),
            has_complained=True,
            complaint_date=date(2026, 10, 1),
            business_replied=False,
        )
        result = screen_case(request)
        self.assertEqual(result["scope"], ["R03", "R04", "R05", "R07", "R08"])
        verdicts = {item["code"]: item["verdict"] for item in result["results"]}
        self.assertEqual(verdicts["R03"], "無此障礙")
        for code in ("R04", "R05", "R07", "R08"):
            self.assertEqual(verdicts[code], "資料不足")

    def test_validates_calendar_dates(self):
        with self.assertRaises(ValueError):
            ScreeningRequest(application_date="not-a-date")

    def test_current_page_maps_unavailable_facts_to_unknown(self):
        page = (PROJECT_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("fetch('/api/v1/screening'", page)
        self.assertIn("complaint_received_date: null", page)
        self.assertIn("prior_evaluation: null", page)
        self.assertIn("proceedings: null", page)

    def test_no_complaint_is_sent_to_engine_as_a_known_no(self):
        result = screen_case(ScreeningRequest(
            application_date=date(2026, 11, 15), has_complained=False
        ))
        r03 = next(item for item in result["results"] if item["code"] == "R03")
        self.assertEqual(r03["verdict"], "有障礙")

    def test_mounts_screening_route(self):
        self.assertIn("/api/v1/screening", app.openapi()["paths"])


if __name__ == "__main__":
    unittest.main()

