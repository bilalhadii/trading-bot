"""Focused tests for the separate reclaim experiment."""
import unittest
from unittest.mock import patch

import test_orb_retest as fixtures
from strategy.signals import (
    find_first_orb_breakout,
    find_first_orb_retest,
    find_first_orb_retest_reclaim,
)


def detect(rows, short=False, max_bars=5, fraction=0.10):
    return find_first_orb_retest_reclaim(
        fixtures.candles(rows, short), 110, 100, max_bars, fraction
    )


class ReclaimTests(unittest.TestCase):
    def test_long_and_short_reclaim_enter_next_open(self):
        for short in (False, True):
            rows = [fixtures.BREAKOUT, fixtures.RETEST, fixtures.ENTRY]
            df = fixtures.candles(rows, short)
            result = detect(rows, short)
            self.assertEqual(result['direction'], 'SHORT' if short else 'LONG')
            self.assertEqual(result['retest_timestamp'], df.iloc[1].timestamp_ny)
            self.assertEqual(result['confirmation_timestamp'], df.iloc[1].timestamp_ny)
            self.assertEqual(result['entry_timestamp'], df.iloc[2].timestamp_ny)
            self.assertEqual(result['entry_price'], df.iloc[2].open)

    def test_first_overlap_wrong_side_or_equal_fails_without_retry(self):
        for short in (False, True):
            for close in (109.5, 110):
                failed = (111, 112, 109.5, close)
                rows = [fixtures.BREAKOUT, failed, fixtures.RETEST, fixtures.CONFIRM, fixtures.ENTRY]
                self.assertIsNone(detect(rows, short))
                # Original retest can still confirm later on these same candles.
                self.assertIsNotNone(find_first_orb_retest(fixtures.candles(rows, short), 110, 100, 5, .10))

    def test_no_retest_or_late_retest_fails(self):
        for short in (False, True):
            self.assertIsNone(detect([fixtures.BREAKOUT] + [fixtures.AWAY]*7, short))
            self.assertIsNone(detect([fixtures.BREAKOUT] + [fixtures.AWAY]*5 + [fixtures.RETEST, fixtures.ENTRY], short))

    def test_fifth_bar_reclaim_allows_sixth_bar_entry(self):
        for short in (False, True):
            result = detect([fixtures.BREAKOUT] + [fixtures.AWAY]*4 + [fixtures.RETEST, fixtures.ENTRY], short)
            self.assertEqual(result['confirmation_timestamp'].minute, 40)
            self.assertEqual(result['entry_timestamp'].minute, 41)

    def test_no_next_candle_no_entry(self):
        self.assertIsNone(detect([fixtures.BREAKOUT, fixtures.RETEST]))

    def test_invalidation_ends_first_breakout_setup(self):
        for short in (False, True):
            invalid = (108.5, 108.9, 108, 108.5)
            self.assertIsNone(detect([fixtures.BREAKOUT, invalid, fixtures.BREAKOUT, fixtures.RETEST, fixtures.ENTRY], short))

    def test_inclusive_band_and_explicit_parameters(self):
        edge = (112, 112.5, 111, 111.5)
        for short in (False, True):
            result = detect([fixtures.BREAKOUT, edge, fixtures.ENTRY], short)
            self.assertEqual(result['retest_tolerance'], 1.0)
            self.assertIsNone(detect([fixtures.BREAKOUT, edge, fixtures.ENTRY], short, fraction=.05))
            rows = [fixtures.BREAKOUT, fixtures.AWAY, fixtures.RETEST, fixtures.ENTRY]
            self.assertIsNone(detect(rows, short, max_bars=1))
            self.assertIsNotNone(detect(rows, short, max_bars=2))

    def test_three_distinct_entry_timings(self):
        for short in (False, True):
            df = fixtures.candles([fixtures.BREAKOUT, fixtures.RETEST, fixtures.CONFIRM, fixtures.ENTRY], short)
            baseline = find_first_orb_breakout(df, 110, 100)
            retest = find_first_orb_retest(df, 110, 100, 5, .10)
            reclaim = find_first_orb_retest_reclaim(df, 110, 100, 5, .10)
            self.assertEqual(baseline['entry_timestamp'], df.iloc[1].timestamp_ny)
            self.assertEqual(reclaim['entry_timestamp'], df.iloc[2].timestamp_ny)
            self.assertEqual(retest['entry_timestamp'], df.iloc[3].timestamp_ny)

    def test_runner_dispatch_risk_target_signal_time_and_one_trade(self):
        for short in (False, True):
            trades = fixtures.RunnerTests().run_fixture('ORB_RETEST_RECLAIM_2R', short)
            self.assertEqual(len(trades), 1)
            trade = trades[0]
            self.assertEqual(trade['signal_time'].minute, 36)
            self.assertEqual(trade['entry_time'].minute, 37)
            self.assertEqual(trade['direction'], 'SHORT' if short else 'LONG')
            self.assertEqual(trade['entry_price'], 98 if short else 112)
            self.assertEqual(trade['stop_price'], 110 if short else 100)
            self.assertEqual(trade['risk_amount'], 12)
            self.assertEqual(trade['target_price'], 74 if short else 136)
            self.assertEqual(trade['outcome'], 'SESSION_CLOSE')

    def test_runner_nonpositive_directional_risk_skips(self):
        for short in (False, True):
            for entry in (99, 100):
                with patch.object(fixtures, 'CONFIRM', (entry, entry+1, entry-1, entry)):
                    self.assertEqual(fixtures.RunnerTests().run_fixture('ORB_RETEST_RECLAIM_2R', short), [])


if __name__ == '__main__':
    unittest.main()
