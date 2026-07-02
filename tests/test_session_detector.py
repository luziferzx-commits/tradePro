import unittest
from datetime import datetime, timezone
from market.session_detector import SessionDetector

class TestSessionDetector(unittest.TestCase):

    def _get_timestamp(self, hour: int, minute: int) -> float:
        dt = datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc)
        return dt.timestamp()

    def test_asia_session(self):
        ts = self._get_timestamp(3, 30)
        self.assertEqual(SessionDetector.detect(ts), "ASIA")

    def test_london_session(self):
        ts = self._get_timestamp(9, 0)
        self.assertEqual(SessionDetector.detect(ts), "LONDON")

    def test_london_ny_overlap(self):
        ts = self._get_timestamp(14, 30)
        self.assertEqual(SessionDetector.detect(ts), "LONDON_NY_OVERLAP")

    def test_new_york_session(self):
        ts = self._get_timestamp(18, 0)
        self.assertEqual(SessionDetector.detect(ts), "NEW_YORK")

    def test_off_session(self):
        ts = self._get_timestamp(22, 0)
        self.assertEqual(SessionDetector.detect(ts), "OFF_SESSION")

    def test_analyze_session(self):
        ts = self._get_timestamp(14, 30) # 1 hour 30 mins after Overlap open (13:00)
        info = SessionDetector.analyze_session(ts)
        self.assertEqual(info["session_label"], "LONDON_NY_OVERLAP")
        self.assertEqual(info["is_overlap_session"], True)
        self.assertEqual(info["minutes_from_session_open"], 90)

if __name__ == '__main__':
    unittest.main()
