"""
Unit tests for p1p2_detect — pure detection functions, no DB required.

Test candles use a 1-day timeframe with hourly sub-candles so that
time_pct values are clean multiples of (1/24 × 100 ≈ 4.167%).

Candle:  2025-01-01 00:00 UTC  →  2025-01-02 00:00 UTC  (24 h)
t_pct(h) = h / 24 × 100   e.g. hour 6 → 25.00 %
"""

import unittest
from datetime import datetime, timezone

from app.services.p1p2_detect import (
    SubCandle,
    candle_close_time,
    detect_p1_p2,
)

UTC = timezone.utc

# ── Helpers ────────────────────────────────────────────────────────────────────

OPEN_TIME = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
TF = "1d"


def _sub(hour: int, high: float, low: float) -> SubCandle:
    """Build a minimal sub-candle at the given hour offset."""
    mid = (high + low) / 2
    return SubCandle(
        open_time=datetime(2025, 1, 1, hour, 0, 0, tzinfo=UTC),
        open=mid,
        high=high,
        low=low,
        close=mid,
    )


def _detect(sub_candles, open_price=100.0, close=100.0):
    """Thin wrapper so tests don't repeat boilerplate."""
    # Derive high/low from sub-candles (matches what the caller would supply)
    h = max(s.high for s in sub_candles) if sub_candles else open_price
    l = min(s.low for s in sub_candles) if sub_candles else open_price
    return detect_p1_p2(
        open_price=open_price,
        high=h,
        low=l,
        close=close,
        candle_open_time=OPEN_TIME,
        timeframe=TF,
        sub_candles=sub_candles,
    )


# ── candle_close_time ──────────────────────────────────────────────────────────

class TestCandleCloseTime(unittest.TestCase):

    def test_1h(self):
        t = datetime(2025, 1, 1, 5, 0, 0, tzinfo=UTC)
        self.assertEqual(candle_close_time(t, "1h"), datetime(2025, 1, 1, 6, 0, 0, tzinfo=UTC))

    def test_4h(self):
        t = datetime(2025, 1, 1, 8, 0, 0, tzinfo=UTC)
        self.assertEqual(candle_close_time(t, "4h"), datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC))

    def test_1d(self):
        t = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        self.assertEqual(candle_close_time(t, "1d"), datetime(2025, 1, 2, 0, 0, 0, tzinfo=UTC))

    def test_1w(self):
        t = datetime(2025, 1, 6, 0, 0, 0, tzinfo=UTC)
        self.assertEqual(candle_close_time(t, "1w"), datetime(2025, 1, 13, 0, 0, 0, tzinfo=UTC))

    def test_1mo_mid_year(self):
        t = datetime(2025, 3, 1, 0, 0, 0, tzinfo=UTC)
        self.assertEqual(candle_close_time(t, "1mo"), datetime(2025, 4, 1, 0, 0, 0, tzinfo=UTC))

    def test_1mo_december_wraps_year(self):
        t = datetime(2025, 12, 1, 0, 0, 0, tzinfo=UTC)
        self.assertEqual(candle_close_time(t, "1mo"), datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC))

    def test_unknown_timeframe_raises(self):
        t = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        with self.assertRaises(ValueError):
            candle_close_time(t, "5m")


# ── Empty / degenerate input ───────────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_empty_sub_candles_returns_none(self):
        self.assertIsNone(_detect([]))

    def test_flat_price_never_leaves_open_returns_none(self):
        # Sub-candles that never cross the open price
        subs = [_sub(h, high=100.0, low=100.0) for h in range(24)]
        self.assertIsNone(_detect(subs, open_price=100.0))


# ── P1 = low, no flip (clean bullish candle) ──────────────────────────────────

class TestP1LowNoFlip(unittest.TestCase):
    """
    Hour 0 : price drops to 95  → P1 = low @ 95  (first move is downward)
    Hour 6 : price rises to 110 → P2 = high @ 110 (ultimate high, first at H6)
    No sub-candle goes below 95 after H0 → no flip.
    """

    def setUp(self):
        subs = [
            _sub(0,  high=100.0, low=95.0),   # H0: breaks below open → P1=low
            _sub(6,  high=110.0, low=96.0),   # H6: new high (ultimate)
            _sub(12, high=108.0, low=97.0),   # H12: nothing new
            _sub(18, high=105.0, low=98.0),   # H18: nothing new
        ]
        self.r = _detect(subs, open_price=100.0, close=108.0)

    def test_p1_side(self):
        self.assertEqual(self.r.p1_side, "low")

    def test_p1_price(self):
        self.assertAlmostEqual(self.r.p1_price, 95.0)

    def test_p1_time_pct(self):
        # H0 → 0/24 × 100 = 0.0 %
        self.assertAlmostEqual(self.r.p1_time_pct, 0.0)

    def test_p1_dist_pct(self):
        # (95 - 100) / 100 × 100 = −5.0
        self.assertAlmostEqual(self.r.p1_dist_pct, -5.0)

    def test_no_flip(self):
        self.assertEqual(self.r.p1_flip_count, 0)
        self.assertFalse(self.r.p1_flip_occurred)

    def test_final_p1_equals_original(self):
        self.assertAlmostEqual(self.r.final_p1_price, 95.0)
        self.assertAlmostEqual(self.r.final_p1_time_pct, 0.0)

    def test_p2_price(self):
        self.assertAlmostEqual(self.r.p2_price, 110.0)

    def test_p2_time_pct(self):
        # H6 → 6/24 × 100 = 25.0 %
        self.assertAlmostEqual(self.r.p2_time_pct, 25.0)

    def test_p2_dist_pct(self):
        # (110 - 100) / 100 × 100 = 10.0
        self.assertAlmostEqual(self.r.p2_dist_pct, 10.0)

    def test_flags(self):
        self.assertTrue(self.r.is_bullish)    # close 108 > open 100
        self.assertTrue(self.r.low_held)
        self.assertFalse(self.r.high_held)

    def test_sub_candle_count(self):
        self.assertEqual(self.r.sub_candle_count, 4)


# ── P1 = high, no flip (clean bearish candle) ─────────────────────────────────

class TestP1HighNoFlip(unittest.TestCase):
    """
    Hour 0 : price rises to 112 → P1 = high @ 112 (first move is upward)
    Hour 18: price drops to 82  → P2 = low @ 82
    No sub-candle exceeds 112 after H0 → no flip.
    """

    def setUp(self):
        subs = [
            _sub(0,  high=112.0, low=100.0),  # H0: breaks above open → P1=high
            _sub(6,  high=111.0, low=96.0),   # H6: lower high, falling
            _sub(12, high=108.0, low=88.0),   # H12: continues down
            _sub(18, high=105.0, low=82.0),   # H18: ultimate low
        ]
        self.r = _detect(subs, open_price=100.0, close=85.0)

    def test_p1_side(self):
        self.assertEqual(self.r.p1_side, "high")

    def test_p1_price(self):
        self.assertAlmostEqual(self.r.p1_price, 112.0)

    def test_p1_dist_pct(self):
        # (112 - 100) / 100 × 100 = 12.0
        self.assertAlmostEqual(self.r.p1_dist_pct, 12.0)

    def test_no_flip(self):
        self.assertEqual(self.r.p1_flip_count, 0)
        self.assertFalse(self.r.p1_flip_occurred)

    def test_p2_price(self):
        self.assertAlmostEqual(self.r.p2_price, 82.0)

    def test_p2_time_pct(self):
        # H18 → 18/24 × 100 = 75.0 %
        self.assertAlmostEqual(self.r.p2_time_pct, 75.0)

    def test_flags(self):
        self.assertFalse(self.r.is_bullish)   # close 85 < open 100
        self.assertFalse(self.r.low_held)
        self.assertTrue(self.r.high_held)


# ── P1 = low, single flip ─────────────────────────────────────────────────────

class TestP1LowOneFlip(unittest.TestCase):
    """
    Hour  0: drops to 96  → P1 = low @ 96
    Hour  6: rises to 110 → starts forming opposite extreme
    Hour 12: new low at 91  → FLIP #1, final P1 = 91
    low_held = False (flip occurred).
    """

    def setUp(self):
        subs = [
            _sub(0,  high=100.0, low=96.0),   # H0: P1=low@96
            _sub(6,  high=110.0, low=97.0),   # H6: high (will be P2)
            _sub(12, high=104.0, low=91.0),   # H12: new low → flip
            _sub(18, high=103.0, low=92.0),   # H18: no further flip
        ]
        self.r = _detect(subs, open_price=100.0, close=95.0)

    def test_p1_side(self):
        self.assertEqual(self.r.p1_side, "low")

    def test_original_p1_price(self):
        self.assertAlmostEqual(self.r.p1_price, 96.0)

    def test_flip_count(self):
        self.assertEqual(self.r.p1_flip_count, 1)
        self.assertTrue(self.r.p1_flip_occurred)

    def test_final_p1_price(self):
        self.assertAlmostEqual(self.r.final_p1_price, 91.0)

    def test_final_p1_time_pct(self):
        # H12 → 12/24 × 100 = 50.0 %
        self.assertAlmostEqual(self.r.final_p1_time_pct, 50.0)

    def test_low_held_false(self):
        self.assertFalse(self.r.low_held)

    def test_p2_price(self):
        # Ultimate high across all sub-candles = 110 (H6)
        self.assertAlmostEqual(self.r.p2_price, 110.0)


# ── P1 = high, double flip ────────────────────────────────────────────────────

class TestP1HighDoubleFlip(unittest.TestCase):
    """
    Hour  0: rises to 108  → P1 = high @ 108
    Hour  4: new high 112  → FLIP #1, final P1 = 112
    Hour  8: new high 118  → FLIP #2, final P1 = 118
    Hour 20: low 82        → P2 = low @ 82
    high_held = False (two flips).
    """

    def setUp(self):
        subs = [
            _sub(0,  high=108.0, low=100.0),  # H0: P1=high@108
            _sub(4,  high=112.0, low=100.0),  # H4: flip #1 → 112
            _sub(8,  high=118.0, low=100.0),  # H8: flip #2 → 118
            _sub(12, high=115.0, low=95.0),   # H12: not a new high
            _sub(20, high=110.0, low=82.0),   # H20: ultimate low
        ]
        self.r = _detect(subs, open_price=100.0, close=105.0)

    def test_p1_side(self):
        self.assertEqual(self.r.p1_side, "high")

    def test_flip_count(self):
        self.assertEqual(self.r.p1_flip_count, 2)

    def test_final_p1_price(self):
        self.assertAlmostEqual(self.r.final_p1_price, 118.0)

    def test_final_p1_time_pct(self):
        # H8 → 8/24 × 100 = 33.33 %
        self.assertAlmostEqual(self.r.final_p1_time_pct, round(8 / 24 * 100, 2))

    def test_high_held_false(self):
        self.assertFalse(self.r.high_held)

    def test_p2_price(self):
        self.assertAlmostEqual(self.r.p2_price, 82.0)

    def test_p2_time_pct(self):
        # H20 → 20/24 × 100 = 83.33 %
        self.assertAlmostEqual(self.r.p2_time_pct, round(20 / 24 * 100, 2))


# ── Tiebreaker: both extremes in the first sub-candle ─────────────────────────

class TestTiebreaker(unittest.TestCase):

    def test_larger_downside_wins(self):
        """low_dist > high_dist → P1 = low."""
        subs = [_sub(0, high=108.0, low=80.0)]  # low_dist=20 > high_dist=8
        r = _detect(subs, open_price=100.0, close=100.0)
        self.assertEqual(r.p1_side, "low")
        self.assertAlmostEqual(r.p1_price, 80.0)

    def test_larger_upside_wins(self):
        """high_dist > low_dist → P1 = high."""
        subs = [_sub(0, high=125.0, low=90.0)]  # high_dist=25 > low_dist=10
        r = _detect(subs, open_price=100.0, close=100.0)
        self.assertEqual(r.p1_side, "high")
        self.assertAlmostEqual(r.p1_price, 125.0)

    def test_exact_tie_high_wins(self):
        """Exact tie (equal distances) → P1 = high (>= condition in code)."""
        subs = [_sub(0, high=110.0, low=90.0)]  # both dist=10
        r = _detect(subs, open_price=100.0, close=100.0)
        self.assertEqual(r.p1_side, "high")


# ── P2 is the first sub-candle that touched the ultimate opposite extreme ──────

class TestP2FirstOccurrence(unittest.TestCase):
    """
    Two sub-candles reach the same maximum high — P2 time should be the FIRST.
    """

    def test_p2_picks_first_occurrence(self):
        subs = [
            _sub(0,  high=100.0, low=90.0),   # H0: P1=low@90
            _sub(6,  high=115.0, low=91.0),   # H6: ultimate high = 115 (first)
            _sub(12, high=115.0, low=92.0),   # H12: same high (second)
        ]
        r = _detect(subs, open_price=100.0, close=112.0)
        # P2 time should be H6, not H12
        expected = datetime(2025, 1, 1, 6, 0, 0, tzinfo=UTC)
        self.assertEqual(r.p2_time, expected)


# ── Flip does not move P2 ──────────────────────────────────────────────────────

class TestFlipDoesNotAffectP2(unittest.TestCase):
    """
    Even after a flip, P2 remains the ultimate opposite extreme.
    The flip only updates final_p1_price; it does not redefine P2.
    """

    def test_p2_unchanged_after_flip(self):
        subs = [
            _sub(0,  high=100.0, low=95.0),   # H0: P1=low@95
            _sub(6,  high=114.0, low=96.0),   # H6: ultimate high (P2=114)
            _sub(12, high=102.0, low=88.0),   # H12: flip → final P1=88
        ]
        r = _detect(subs, open_price=100.0, close=90.0)
        self.assertAlmostEqual(r.p2_price, 114.0)       # still 114
        self.assertEqual(r.p1_flip_count, 1)
        self.assertAlmostEqual(r.final_p1_price, 88.0)


# ── is_bullish flag ────────────────────────────────────────────────────────────

class TestIsBullish(unittest.TestCase):

    def test_bullish_close(self):
        subs = [_sub(0, high=100.0, low=95.0), _sub(6, high=110.0, low=96.0)]
        r = _detect(subs, open_price=100.0, close=108.0)
        self.assertTrue(r.is_bullish)

    def test_bearish_close(self):
        subs = [_sub(0, high=100.0, low=95.0), _sub(6, high=110.0, low=96.0)]
        r = _detect(subs, open_price=100.0, close=94.0)
        self.assertFalse(r.is_bullish)

    def test_doji_close_equals_open(self):
        subs = [_sub(0, high=100.0, low=95.0), _sub(6, high=110.0, low=96.0)]
        r = _detect(subs, open_price=100.0, close=100.0)
        self.assertFalse(r.is_bullish)  # close == open → not bullish


if __name__ == "__main__":
    unittest.main()
