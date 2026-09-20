"""Focused tests for the reclaim-body experiment."""
import unittest

import test_orb_retest as fixtures
from strategy.signals import (
    find_first_orb_breakout,
    find_first_orb_retest,
    find_first_orb_retest_reclaim,
    find_first_orb_retest_reclaim_body,
    find_first_orb_retest_reclaim_body_rejection_reason,
)


BODY_RECLAIM = (111, 112.5, 110.5, 111.5)


def detect(rows, short=False, max_bars=5, fraction=0.10):
    return find_first_orb_retest_reclaim_body(
        fixtures.candles(rows, short), 110, 100, max_bars, fraction
    )


class ReclaimBodyTests(unittest.TestCase):
    def test_long_body_aligned_reclaim_enters_next_open(self):
        rows = [fixtures.BREAKOUT, BODY_RECLAIM, fixtures.ENTRY]
        df = fixtures.candles(rows)
        result = detect(rows)
        self.assertEqual(result["direction"], "LONG")
        self.assertEqual(result["retest_timestamp"], df.iloc[1].timestamp_ny)
        self.assertEqual(result["confirmation_timestamp"], df.iloc[1].timestamp_ny)
        self.assertEqual(result["entry_timestamp"], df.iloc[2].timestamp_ny)
        self.assertEqual(result["entry_price"], df.iloc[2].open)

    def test_short_body_aligned_reclaim_enters_next_open(self):
        rows = [fixtures.BREAKOUT, BODY_RECLAIM, fixtures.ENTRY]
        df = fixtures.candles(rows, short=True)
        result = detect(rows, short=True)
        self.assertEqual(result["direction"], "SHORT")
        self.assertEqual(result["retest_timestamp"], df.iloc[1].timestamp_ny)
        self.assertEqual(result["confirmation_timestamp"], df.iloc[1].timestamp_ny)
        self.assertEqual(result["entry_timestamp"], df.iloc[2].timestamp_ny)
        self.assertEqual(result["entry_price"], df.iloc[2].open)

    def test_long_bearish_body_reclaim_is_rejected_without_retry(self):
        bearish_reclaim = (112, 112.5, 110.5, 111.5)
        bullish_reclaim = (111, 112.5, 110.5, 111.5)
        rows = [fixtures.BREAKOUT, bearish_reclaim, bullish_reclaim, fixtures.ENTRY]
        self.assertIsNone(detect(rows))
        reason = find_first_orb_retest_reclaim_body_rejection_reason(
            fixtures.candles(rows), 110, 100, 5, .10
        )
        self.assertEqual(reason, "BODY_DISAGREEMENT")

    def test_short_bullish_body_reclaim_is_rejected_without_retry(self):
        bullish_reclaim = fixtures.RETEST
        rows = [fixtures.BREAKOUT, bullish_reclaim, BODY_RECLAIM, fixtures.ENTRY]
        self.assertIsNone(detect(rows, short=True))
        reason = find_first_orb_retest_reclaim_body_rejection_reason(
            fixtures.candles(rows, short=True), 110, 100, 5, .10
        )
        self.assertEqual(reason, "BODY_DISAGREEMENT")

    def test_no_retest_is_rejected(self):
        for short in (False, True):
            self.assertIsNone(detect([fixtures.BREAKOUT] + [fixtures.AWAY] * 7, short))

    def test_fifth_bar_reclaim_allows_next_open_entry(self):
        for short in (False, True):
            result = detect(
                [fixtures.BREAKOUT] + [fixtures.AWAY] * 4 + [BODY_RECLAIM, fixtures.ENTRY],
                short,
            )
            self.assertEqual(result["confirmation_timestamp"].minute, 40)
            self.assertEqual(result["entry_timestamp"].minute, 41)

    def test_sixth_bar_reclaim_is_too_late(self):
        for short in (False, True):
            self.assertIsNone(
                detect([fixtures.BREAKOUT] + [fixtures.AWAY] * 5 + [BODY_RECLAIM, fixtures.ENTRY], short)
            )

    def test_distinct_existing_strategy_timings_remain_unchanged(self):
        for short in (False, True):
            df = fixtures.candles(
                [fixtures.BREAKOUT, BODY_RECLAIM, fixtures.CONFIRM, fixtures.ENTRY],
                short,
            )
            baseline = find_first_orb_breakout(df, 110, 100)
            retest = find_first_orb_retest(df, 110, 100, 5, .10)
            reclaim = find_first_orb_retest_reclaim(df, 110, 100, 5, .10)
            body = find_first_orb_retest_reclaim_body(df, 110, 100, 5, .10)
            self.assertEqual(baseline["entry_timestamp"], df.iloc[1].timestamp_ny)
            self.assertEqual(reclaim["entry_timestamp"], df.iloc[2].timestamp_ny)
            self.assertEqual(body["entry_timestamp"], df.iloc[2].timestamp_ny)
            self.assertEqual(retest["entry_timestamp"], df.iloc[3].timestamp_ny)

    def test_runner_dispatches_new_version(self):
        for short in (False, True):
            with unittest.mock.patch.object(fixtures, "RETEST", BODY_RECLAIM):
                trades = fixtures.RunnerTests().run_fixture("ORB_RETEST_RECLAIM_BODY_2R", short)
            self.assertEqual(len(trades), 1)
            trade = trades[0]
            self.assertEqual(trade["signal_time"].minute, 36)
            self.assertEqual(trade["entry_time"].minute, 37)
            self.assertEqual(trade["direction"], "SHORT" if short else "LONG")


if __name__ == "__main__":
    unittest.main()
