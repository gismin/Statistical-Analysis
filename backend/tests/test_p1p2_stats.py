"""
Unit tests for p1p2_stats — pure statistics functions.

No DB, no async.  P1P2Stats model objects are built directly in memory
(SQLAlchemy ORM models are plain Python objects outside a session).

Dataset conventions
-------------------
All test datasets use weekly-style data.  Fields irrelevant to a specific
test are set to neutral/zero values to keep tests focused.
"""

import unittest
from datetime import datetime, timezone

from app.models.p1p2_stats import P1P2Stats
from app.services.p1p2_stats import (
    CONFIDENCE_LEVELS,
    RELIABILITY_THRESHOLD,
    build_summary,
    compute_confidence_targets,
    compute_data_quality,
    compute_flip_risk,
    compute_p2_likelihood_dist,
    compute_p2_likelihood_time,
    compute_warnings,
)

UTC = timezone.utc


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row(
    *,
    p1_side: str = "low",
    p1_flip_occurred: bool = False,
    p1_flip_count: int = 0,
    p1_time_pct: float = 10.0,
    p1_dist_pct: float = -5.0,
    p2_time_pct: float = 60.0,
    p2_dist_pct: float = 8.0,
    low_held: bool | None = None,
    high_held: bool | None = None,
    is_bullish: bool = True,
    open_price: float = 100.0,
) -> P1P2Stats:
    """
    Construct a P1P2Stats object with sensible defaults.
    low_held / high_held are auto-derived when not supplied.
    """
    # Auto-derive the flag that wasn't explicitly supplied.
    # If the caller fixes one side, the other side must be False
    # (a candle can't have both low_held and high_held True).
    if low_held is None and high_held is None:
        low_held = p1_side == "low" and not p1_flip_occurred
        high_held = p1_side == "high" and not p1_flip_occurred
    elif low_held is None:
        low_held = False  # caller supplied high_held; low_held must be False
    elif high_held is None:
        high_held = False  # caller supplied low_held; high_held must be False

    row = P1P2Stats(
        symbol="BTC/USDT",
        timeframe="1w",
        candle_open_time=datetime(2025, 1, 6, tzinfo=UTC),
        open_price=open_price,
        high=open_price * 1.10,
        low=open_price * 0.90,
        close=open_price * (1.05 if is_bullish else 0.95),
        p1_side=p1_side,
        p1_price=open_price + open_price * p1_dist_pct / 100,
        p1_time=datetime(2025, 1, 6, 6, tzinfo=UTC),
        p1_dist_pct=p1_dist_pct,
        p1_time_pct=p1_time_pct,
        p1_flip_count=p1_flip_count,
        p1_flip_occurred=p1_flip_occurred,
        final_p1_price=open_price + open_price * p1_dist_pct / 100,
        final_p1_time=datetime(2025, 1, 6, 6, tzinfo=UTC),
        final_p1_dist_pct=p1_dist_pct,
        final_p1_time_pct=p1_time_pct,
        p2_price=open_price + open_price * p2_dist_pct / 100,
        p2_time=datetime(2025, 1, 8, tzinfo=UTC),
        p2_dist_pct=p2_dist_pct,
        p2_time_pct=p2_time_pct,
        is_bullish=is_bullish,
        low_held=low_held,
        high_held=high_held,
        sub_candle_count=168,
    )
    return row


def _rows(n: int, **kwargs) -> list[P1P2Stats]:
    """Create n identical rows."""
    return [_row(**kwargs) for _ in range(n)]


# ── compute_flip_risk ──────────────────────────────────────────────────────────

class TestFlipRisk(unittest.TestCase):

    def test_empty_dataset(self):
        r = compute_flip_risk([])
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["pct"], 0.0)
        self.assertEqual(r["label"], "low")

    def test_zero_flips(self):
        rows = _rows(10, p1_flip_occurred=False)
        r = compute_flip_risk(rows)
        self.assertEqual(r["flipped"], 0)
        self.assertEqual(r["pct"], 0.0)
        self.assertEqual(r["label"], "low")

    def test_low_risk_below_30(self):
        rows = (
            _rows(2, p1_flip_occurred=True) +
            _rows(8, p1_flip_occurred=False)
        )   # 20 % → low
        r = compute_flip_risk(rows)
        self.assertAlmostEqual(r["pct"], 20.0)
        self.assertEqual(r["label"], "low")

    def test_moderate_risk_30_to_50(self):
        rows = (
            _rows(4, p1_flip_occurred=True) +
            _rows(6, p1_flip_occurred=False)
        )   # 40 % → moderate
        r = compute_flip_risk(rows)
        self.assertAlmostEqual(r["pct"], 40.0)
        self.assertEqual(r["label"], "moderate")

    def test_high_risk_above_50(self):
        rows = (
            _rows(6, p1_flip_occurred=True) +
            _rows(4, p1_flip_occurred=False)
        )   # 60 % → high
        r = compute_flip_risk(rows)
        self.assertAlmostEqual(r["pct"], 60.0)
        self.assertEqual(r["label"], "high")

    def test_exactly_50_pct_is_high(self):
        rows = _rows(10, p1_flip_occurred=True)  # 100 % → high
        r = compute_flip_risk(rows)
        self.assertEqual(r["label"], "high")

    def test_total_count(self):
        rows = _rows(42, p1_flip_occurred=False)
        r = compute_flip_risk(rows)
        self.assertEqual(r["total"], 42)


# ── compute_p2_likelihood_time ─────────────────────────────────────────────────

class TestP2LikelihoodTime(unittest.TestCase):

    def test_empty_returns_insufficient(self):
        r = compute_p2_likelihood_time([], current_time_pct=50.0)
        self.assertEqual(r["message"], "Insufficient data")

    def test_all_p2s_formed_before_current(self):
        # All sessions have p2_time_pct = 20, current = 80 → 100 % formed
        rows = _rows(10, p2_time_pct=20.0)
        r = compute_p2_likelihood_time(rows, current_time_pct=80.0)
        self.assertAlmostEqual(r["pct_formed_by_now"], 100.0)
        self.assertIn("100.0%", r["message"])

    def test_no_p2_formed_yet(self):
        # All p2_time_pct = 90, current = 10 → 0 % formed
        rows = _rows(10, p2_time_pct=90.0)
        r = compute_p2_likelihood_time(rows, current_time_pct=10.0)
        self.assertAlmostEqual(r["pct_formed_by_now"], 0.0)
        self.assertIn("Unlikely", r["message"])

    def test_half_formed(self):
        # 5 sessions have p2_time_pct = 30, 5 have 70; current = 50
        rows = (
            _rows(5, p2_time_pct=30.0) +
            _rows(5, p2_time_pct=70.0)
        )
        r = compute_p2_likelihood_time(rows, current_time_pct=50.0)
        self.assertAlmostEqual(r["pct_formed_by_now"], 50.0)
        self.assertIn("Unclear", r["message"])

    def test_median_and_p90_computed(self):
        # 10 sessions with p2_time_pct 10..100 (step 10)
        rows = [_row(p2_time_pct=float(i * 10)) for i in range(1, 11)]
        r = compute_p2_likelihood_time(rows, current_time_pct=50.0)
        # Median: sorted[5] = 60.0 (0-indexed middle of 10 items)
        self.assertAlmostEqual(r["p2_median_time_pct"], 60.0)
        # p90 index = int(0.90 * 10) = 9 → sorted[9] = 100
        self.assertAlmostEqual(r["p2_p90_time_pct"], 100.0)

    def test_boundary_exactly_90_pct_message(self):
        # 9 of 10 rows have p2_time_pct <= 50
        rows = _rows(9, p2_time_pct=20.0) + _rows(1, p2_time_pct=80.0)
        r = compute_p2_likelihood_time(rows, current_time_pct=50.0)
        self.assertAlmostEqual(r["pct_formed_by_now"], 90.0)
        # 90 % → "X% of sessions would have P2 in by now"
        self.assertNotIn("Unlikely", r["message"])
        self.assertNotIn("Unclear", r["message"])


# ── compute_p2_likelihood_dist ─────────────────────────────────────────────────

class TestP2LikelihoodDist(unittest.TestCase):

    def test_empty_returns_insufficient(self):
        r = compute_p2_likelihood_dist([], current_dist_abs=5.0)
        self.assertEqual(r["message"], "Insufficient data")

    def test_all_moved_further(self):
        # All sessions have |p2_dist_pct| = 15, current = 3 → 100 % further
        rows = _rows(10, p2_dist_pct=15.0)
        r = compute_p2_likelihood_dist(rows, current_dist_abs=3.0)
        self.assertAlmostEqual(r["pct_moved_further"], 100.0)
        self.assertIn("100.0%", r["message"])

    def test_none_moved_further(self):
        # All sessions have |p2_dist_pct| = 3, current = 10 → 0 % further
        rows = _rows(10, p2_dist_pct=3.0)
        r = compute_p2_likelihood_dist(rows, current_dist_abs=10.0)
        self.assertAlmostEqual(r["pct_moved_further"], 0.0)
        self.assertIn("Only", r["message"])

    def test_handles_negative_p2_dist_pct(self):
        # Short sessions: p2_dist_pct is negative; abs() should be used
        rows = _rows(10, p1_side="high", p2_dist_pct=-12.0, p1_flip_occurred=False)
        r = compute_p2_likelihood_dist(rows, current_dist_abs=5.0)
        # abs(-12) = 12 > 5 → 100 % moved further
        self.assertAlmostEqual(r["pct_moved_further"], 100.0)

    def test_median_dist_computed(self):
        dists = [float(i) for i in range(1, 11)]  # 1..10
        rows = [_row(p2_dist_pct=d) for d in dists]
        r = compute_p2_likelihood_dist(rows, current_dist_abs=0.0)
        # sorted[5] = 6.0 (median of 10 items, 0-indexed)
        self.assertAlmostEqual(r["p2_median_dist_abs"], 6.0)


# ── compute_warnings ──────────────────────────────────────────────────────────

class TestWarnings(unittest.TestCase):

    def test_no_warnings_when_both_below_threshold(self):
        # P1s concentrated early (p1_time_pct=5), current=50 → few form after 50
        rows = _rows(10, p1_time_pct=5.0, p1_dist_pct=-8.0)
        r = compute_warnings(rows, current_p1_time_pct=50.0, current_p1_dist_abs=10.0)
        self.assertIsNone(r["time_warning"])
        self.assertIsNone(r["dist_warning"])
        self.assertFalse(r["triggered"])

    def test_time_warning_fires_above_30_pct(self):
        # 40 % of P1s form after current_time_pct=20
        rows = _rows(6, p1_time_pct=50.0) + _rows(4, p1_time_pct=10.0)
        r = compute_warnings(rows, current_p1_time_pct=20.0, current_p1_dist_abs=0.0)
        # 6 / 10 = 60 % > 30 % threshold → warning fires
        self.assertIsNotNone(r["time_warning"])
        self.assertIn("60.0%", r["time_warning"])
        self.assertTrue(r["triggered"])

    def test_dist_warning_fires_above_50_pct(self):
        # 80 % of P1s had larger wick than current_p1_dist_abs=2.0
        rows = _rows(8, p1_dist_pct=-10.0) + _rows(2, p1_dist_pct=-1.0)
        r = compute_warnings(rows, current_p1_time_pct=0.0, current_p1_dist_abs=2.0)
        # 8 / 10 = 80 % have |p1_dist_pct| > 2.0 → warning fires
        self.assertIsNotNone(r["dist_warning"])
        self.assertIn("80.0%", r["dist_warning"])
        self.assertTrue(r["triggered"])

    def test_both_warnings_can_fire_simultaneously(self):
        # Many P1s form late AND have larger wicks
        rows = _rows(10, p1_time_pct=80.0, p1_dist_pct=-15.0)
        r = compute_warnings(rows, current_p1_time_pct=10.0, current_p1_dist_abs=3.0)
        self.assertIsNotNone(r["time_warning"])
        self.assertIsNotNone(r["dist_warning"])
        self.assertTrue(r["triggered"])

    def test_dist_warning_uses_absolute_value_for_p1_dist(self):
        # p1_dist_pct is negative (P1=low), should use abs() when comparing
        rows = _rows(10, p1_dist_pct=-8.0)  # abs = 8.0
        # current_p1_dist_abs = 5.0 → 10/10 = 100% have larger wick → fires
        r = compute_warnings(rows, current_p1_time_pct=50.0, current_p1_dist_abs=5.0)
        self.assertIsNotNone(r["dist_warning"])


# ── compute_confidence_targets ─────────────────────────────────────────────────

class TestConfidenceTargets(unittest.TestCase):

    def test_returns_empty_for_insufficient_data(self):
        rows = [_row(low_held=True)]   # only 1 session < 2 minimum
        self.assertEqual(compute_confidence_targets(rows, "long", 100.0), [])

    def test_returns_five_confidence_levels(self):
        rows = _rows(50, low_held=True, p2_dist_pct=10.0)
        targets = compute_confidence_targets(rows, "long", 100.0)
        self.assertEqual(len(targets), 5)
        confidences = [t["confidence"] for t in targets]
        self.assertEqual(confidences, CONFIDENCE_LEVELS)

    def test_long_targets_above_open(self):
        rows = _rows(20, low_held=True, p2_dist_pct=10.0, open_price=100.0)
        targets = compute_confidence_targets(rows, "long", 100.0)
        for t in targets:
            self.assertGreater(t["price"], 100.0)

    def test_short_targets_below_open(self):
        rows = _rows(20, high_held=True, p2_dist_pct=-10.0, open_price=100.0)
        targets = compute_confidence_targets(rows, "short", 100.0)
        for t in targets:
            self.assertLess(t["price"], 100.0)

    def test_higher_confidence_gives_lower_target_for_long(self):
        # 90 % confidence → must be more conservative (smaller gain) than 50 %
        rows = [_row(low_held=True, p2_dist_pct=float(i)) for i in range(1, 21)]
        targets = compute_confidence_targets(rows, "long", 100.0)
        prices = [t["price"] for t in targets]
        # Prices should be non-decreasing from 90→50 % confidence
        self.assertEqual(prices, sorted(prices))

    def test_higher_confidence_gives_higher_target_for_short(self):
        # 90 % confidence short → more conservative (smaller drop) than 50 %
        rows = [_row(high_held=True, p2_dist_pct=-float(i)) for i in range(1, 21)]
        targets = compute_confidence_targets(rows, "short", 100.0)
        prices = [t["price"] for t in targets]
        # Short prices should be non-increasing from 90→50 % confidence
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_90_pct_confidence_correct_math(self):
        # 10 sessions, distances = 1..10 (ascending)
        # 90 % confidence: idx = floor(0.10 * 10) = 1 → distances[1] = 2.0
        # price = 100 * (1 + 2/100) = 102.0
        rows = [_row(low_held=True, p2_dist_pct=float(i), open_price=100.0)
                for i in range(1, 11)]
        targets = compute_confidence_targets(rows, "long", 100.0)
        t90 = next(t for t in targets if t["confidence"] == 90)
        self.assertAlmostEqual(t90["dist_pct"], 2.0)
        self.assertAlmostEqual(t90["price"], 102.0)

    def test_50_pct_confidence_correct_math(self):
        # 10 sessions, distances = 1..10
        # 50 % confidence: idx = floor(0.50 * 10) = 5 → distances[5] = 6.0
        # price = 100 * (1 + 6/100) = 106.0
        rows = [_row(low_held=True, p2_dist_pct=float(i), open_price=100.0)
                for i in range(1, 11)]
        targets = compute_confidence_targets(rows, "long", 100.0)
        t50 = next(t for t in targets if t["confidence"] == 50)
        self.assertAlmostEqual(t50["dist_pct"], 6.0)
        self.assertAlmostEqual(t50["price"], 106.0)

    def test_filters_only_low_held_for_long(self):
        # Mix of low_held=True and high_held=True rows
        # Long targets should only use low_held rows
        long_rows = _rows(10, low_held=True, p2_dist_pct=5.0)
        short_rows = _rows(10, high_held=True, p2_dist_pct=-20.0)
        targets = compute_confidence_targets(long_rows + short_rows, "long", 100.0)
        for t in targets:
            self.assertEqual(t["sample_size"], 10)  # only 10 long rows used

    def test_filters_only_high_held_for_short(self):
        long_rows = _rows(5, low_held=True, p2_dist_pct=15.0)
        short_rows = _rows(15, high_held=True, p2_dist_pct=-8.0)
        targets = compute_confidence_targets(long_rows + short_rows, "short", 100.0)
        for t in targets:
            self.assertEqual(t["sample_size"], 15)


# ── compute_data_quality ───────────────────────────────────────────────────────

class TestDataQuality(unittest.TestCase):

    def test_reliable_above_threshold(self):
        rows = _rows(RELIABILITY_THRESHOLD)
        r = compute_data_quality(rows)
        self.assertTrue(r["reliable"])
        self.assertIn("✅", r["message"])

    def test_unreliable_below_threshold(self):
        rows = _rows(RELIABILITY_THRESHOLD - 1)
        r = compute_data_quality(rows)
        self.assertFalse(r["reliable"])
        self.assertIn("⚠️", r["message"])

    def test_exactly_at_threshold_is_reliable(self):
        rows = _rows(RELIABILITY_THRESHOLD)
        r = compute_data_quality(rows)
        self.assertTrue(r["reliable"])

    def test_total_count_matches(self):
        rows = _rows(17)
        r = compute_data_quality(rows)
        self.assertEqual(r["total"], 17)


# ── build_summary ──────────────────────────────────────────────────────────────

class TestBuildSummary(unittest.TestCase):
    """Smoke-test that build_summary returns all expected keys."""

    def test_output_has_all_keys(self):
        rows = _rows(50, p1_flip_occurred=False, p2_time_pct=60.0, p2_dist_pct=8.0)
        result = build_summary(
            rows,
            current_time_pct=40.0,
            current_p1_dist_abs=3.0,
            current_p2_dist_abs=5.0,
        )
        self.assertIn("flip_risk", result)
        self.assertIn("p2_likelihood_time", result)
        self.assertIn("p2_likelihood_dist", result)
        self.assertIn("warnings", result)
        self.assertIn("data_quality", result)

    def test_data_quality_propagates(self):
        rows = _rows(5)
        result = build_summary(rows, 50.0, 3.0, 5.0)
        self.assertFalse(result["data_quality"]["reliable"])

    def test_flip_risk_propagates(self):
        rows = _rows(10, p1_flip_occurred=True)
        result = build_summary(rows, 50.0, 3.0, 5.0)
        self.assertEqual(result["flip_risk"]["label"], "high")


if __name__ == "__main__":
    unittest.main()
