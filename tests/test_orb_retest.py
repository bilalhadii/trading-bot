"""Deterministic retest tests; no database connection or writes required.

Run: .venv/bin/python -B -m unittest discover -s tests -v
"""
import contextlib
import io
import unittest
from unittest.mock import patch

import pandas as pd

from scripts import run_backtest as runner
from strategy.signals import find_first_orb_breakout, find_first_orb_retest


# OHLC; OR high=110, low=100, tolerance=1. Mirror around 105 for SHORT.
BREAKOUT = (111, 113, 110.5, 112)
RETEST = (112, 112.5, 110.5, 111.5)
CONFIRM = (112, 114, 111.5, 113)
ENTRY = (113.25, 114, 112, 113.25)
AWAY = (112, 113, 111.5, 112)
WAIT = (111.5, 112, 110.5, 112)


def candles(rows, short=False):
    if short:
        rows = [(210-o, 210-l, 210-h, 210-c) for o, h, l, c in rows]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df["timestamp_ny"] = pd.date_range(
        "2024-01-03 09:35", periods=len(df), freq="min", tz="America/New_York"
    )
    return df


def detect(rows, short=False, max_bars=5, fraction=0.10):
    return find_first_orb_retest(candles(rows, short), 110, 100, max_bars, fraction)


class RetestSignalTests(unittest.TestCase):
    def test_long_and_short_retest_confirmation_next_open(self):
        for short in (False, True):
            with self.subTest(short=short):
                df = candles([BREAKOUT, RETEST, CONFIRM, ENTRY], short)
                result = detect([BREAKOUT, RETEST, CONFIRM, ENTRY], short)
                self.assertEqual(result["direction"], "SHORT" if short else "LONG")
                self.assertEqual(result["breakout_timestamp"], df.iloc[0].timestamp_ny)
                self.assertEqual(result["retest_timestamp"], df.iloc[1].timestamp_ny)
                self.assertEqual(result["confirmation_timestamp"], df.iloc[2].timestamp_ny)
                self.assertEqual(result["entry_timestamp"], df.iloc[3].timestamp_ny)
                self.assertEqual(result["entry_price"], df.iloc[3].open)

    def test_no_retest_in_five_bars_does_not_accept_later_retest(self):
        for short in (False, True):
            self.assertIsNone(detect([BREAKOUT] + [AWAY] * 5 + [RETEST, CONFIRM, ENTRY], short))

    def test_invalidation_before_or_after_retest_prevents_restart(self):
        invalid = (111, 112, 108, 108.5)
        for short in (False, True):
            for prefix in ([BREAKOUT], [BREAKOUT, RETEST]):
                with self.subTest(short=short, after_retest=len(prefix) == 2):
                    self.assertIsNone(detect(prefix + [invalid, BREAKOUT, RETEST, CONFIRM, ENTRY], short))

    def test_retest_without_confirmation(self):
        for short in (False, True):
            self.assertIsNone(detect([BREAKOUT, RETEST] + [WAIT] * 5, short))

    def test_confirmation_must_be_strict(self):
        equal_to_retest_high = (112, 113, 111, 112.5)
        for short in (False, True):
            self.assertIsNone(detect([BREAKOUT, RETEST] + [equal_to_retest_high] * 5, short))

    def test_confirmation_on_fifth_bar_entry_on_sixth_is_allowed(self):
        for short in (False, True):
            result = detect([BREAKOUT, RETEST, WAIT, WAIT, WAIT, CONFIRM, ENTRY], short)
            self.assertIsNotNone(result)
            self.assertEqual(result["confirmation_timestamp"].minute, 40)
            self.assertEqual(result["entry_timestamp"].minute, 41)

    def test_confirmation_on_sixth_bar_is_too_late(self):
        for short in (False, True):
            self.assertIsNone(detect([BREAKOUT, RETEST, WAIT, WAIT, WAIT, WAIT, CONFIRM, ENTRY], short))

    def test_retest_on_fifth_bar_cannot_confirm_on_same_bar(self):
        self.assertIsNone(detect([BREAKOUT] + [AWAY] * 4 + [RETEST, CONFIRM, ENTRY]))

    def test_confirmation_needs_next_session_candle(self):
        self.assertIsNone(detect([BREAKOUT, RETEST, CONFIRM]))

    def test_tolerance_is_fraction_of_or_range_and_band_is_inclusive(self):
        edge = (112, 112.5, 111, 111.5)
        outside = (112, 112.5, 111.01, 111.5)
        for short in (False, True):
            result = detect([BREAKOUT, edge, CONFIRM, ENTRY], short)
            self.assertEqual(result["retest_tolerance"], 1.0)
            self.assertIsNone(detect([BREAKOUT, outside, CONFIRM, ENTRY], short))
            self.assertIsNone(detect([BREAKOUT, edge, CONFIRM, ENTRY], short, fraction=0.05))
        df = candles([BREAKOUT, RETEST, CONFIRM, ENTRY])
        scaled = df.copy()
        scaled[["open", "high", "low", "close"]] *= 2
        result = find_first_orb_retest(scaled, 220, 200, 5, 0.10)
        self.assertEqual(result["retest_tolerance"], 2.0)

    def test_close_on_invalidation_boundary_is_valid_but_beyond_is_not(self):
        edge = (111, 112.5, 108, 109)
        for short in (False, True):
            self.assertIsNotNone(detect([BREAKOUT, edge, CONFIRM, ENTRY], short))
            invalid = (*edge[:3], 108.99)
            self.assertIsNone(detect([BREAKOUT, invalid, CONFIRM, ENTRY], short))

    def test_first_retest_extreme_is_not_replaced(self):
        first = (111, 114, 110, 111)
        self.assertIsNone(detect([BREAKOUT, first, RETEST, CONFIRM, ENTRY, ENTRY, ENTRY]))

    def test_window_parameter_is_used(self):
        rows = [BREAKOUT, RETEST, WAIT, CONFIRM, ENTRY]
        self.assertIsNone(detect(rows, max_bars=2))
        self.assertIsNotNone(detect(rows, max_bars=3))

    def test_baseline_still_enters_immediately_after_first_breakout(self):
        for short in (False, True):
            df = candles([BREAKOUT, RETEST, CONFIRM, ENTRY], short)
            result = find_first_orb_breakout(df, 110, 100)
            self.assertEqual(result, {
                "direction": "SHORT" if short else "LONG",
                "breakout_timestamp": df.iloc[0].timestamp_ny,
                "breakout_close": float(df.iloc[0].close),
                "entry_timestamp": df.iloc[1].timestamp_ny,
                "entry_price": float(df.iloc[1].open),
                "breakout_high": 110,
                "breakout_low": 100,
            })

    def test_no_breakout_and_unsorted_input(self):
        self.assertIsNone(detect([(105, 110, 100, 105)] * 8))
        df = candles([BREAKOUT, RETEST, CONFIRM, ENTRY])
        self.assertEqual(
            find_first_orb_retest(df.iloc[::-1], 110, 100, 5, 0.10),
            find_first_orb_retest(df, 110, 100, 5, 0.10),
        )


class RunnerTests(unittest.TestCase):
    def run_fixture(self, version, short=False, invalid_entry=False):
        # Warm-up day retains the existing baseline PDH/PDL availability rule.
        warmup = pd.DataFrame([(105, 110, 100, 105)] * 390,
                              columns=["open", "high", "low", "close"])
        warmup["timestamp"] = pd.date_range(
            "2024-01-02 09:30", periods=390, freq="min", tz="America/New_York"
        )
        entry = (99, 100, 98, 99) if invalid_entry else ENTRY
        rows = [(105, 110, 100, 105)] * 5 + [BREAKOUT, RETEST, CONFIRM, entry]
        rows += [ENTRY] * (390 - len(rows))
        session = candles(rows, short).drop(columns="timestamp_ny")
        session["timestamp"] = pd.date_range(
            "2024-01-03 09:30", periods=390, freq="min", tz="America/New_York"
        )
        data = pd.concat([warmup, session], ignore_index=True)
        data["volume"] = 1000
        with patch.object(runner, "load_data", return_value=data), \
                patch.object(runner, "save_trades") as save, \
                patch.object(runner, "STRATEGY_VERSION", version), \
                patch.object(runner, "EXIT_MODE", "FIXED_R"), \
                patch.object(runner, "TARGET_R", 2.0), \
                patch.object(runner, "EARLY_BREAKOUT_ONLY", False), \
                patch.object(runner, "RETEST_MAX_BARS", 5), \
                patch.object(runner, "RETEST_TOLERANCE_OR_FRACTION", 0.10), \
                contextlib.redirect_stdout(io.StringIO()):
            runner.main()
        return save.call_args.args[0]

    def test_runner_dispatch_timestamps_stop_target_and_one_trade(self):
        for short in (False, True):
            for version in ("ORB_BASELINE_2R", "ORB_RETEST_2R"):
                with self.subTest(short=short, version=version):
                    trades = self.run_fixture(version, short)
                    self.assertEqual(len(trades), 1)
                    trade = trades[0]
                    retest = version == "ORB_RETEST_2R"
                    expected_entry = 113.25 if retest else 112
                    if short:
                        expected_entry = 210 - expected_entry
                    stop = 110 if short else 100
                    risk = stop - expected_entry if short else expected_entry - stop
                    self.assertEqual(trade["entry_time"].minute, 38 if retest else 36)
                    self.assertEqual(trade["signal_time"].minute, 37 if retest else 35)
                    self.assertEqual(trade["entry_price"], expected_entry)
                    self.assertEqual(trade["stop_price"], stop)
                    self.assertEqual(trade["risk_amount"], risk)
                    self.assertEqual(trade["target_price"], expected_entry + (-2 if short else 2) * risk)
                    self.assertEqual(trade["outcome"], "SESSION_CLOSE")

    def test_retest_invalid_directional_entry_risk_skips_trade(self):
        for short in (False, True):
            self.assertEqual(self.run_fixture("ORB_RETEST_2R", short, invalid_entry=True), [])


if __name__ == "__main__":
    unittest.main()
