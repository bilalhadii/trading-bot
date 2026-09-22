from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from datetime import date, time
from enum import Enum
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import exchange_calendars as xcals


NEW_YORK_TZ = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
OPENING_RANGE_TIMES = tuple(time(9, minute) for minute in range(30, 35))


class SessionQuality(str, Enum):
    NO_SESSION = "NO_SESSION"
    COMPLETE = "COMPLETE"
    SCHEDULED_EARLY_CLOSE = "SCHEDULED_EARLY_CLOSE"
    DATA_GAP = "DATA_GAP"
    LARGE_DATA_GAP = "LARGE_DATA_GAP"


@dataclass(frozen=True)
class GapBlock:
    start: pd.Timestamp
    end: pd.Timestamp
    minutes: int


@dataclass(frozen=True)
class SessionQualityReport:
    trading_date: date
    quality: SessionQuality
    expected_open: pd.Timestamp | None
    expected_close: pd.Timestamp | None
    expected_bar_count: int
    actual_bar_count: int
    missing_bar_count: int
    unexpected_extra_count: int
    first_actual_bar: pd.Timestamp | None
    last_actual_bar: pd.Timestamp | None
    missing_timestamps: tuple[pd.Timestamp, ...]
    unexpected_extra_timestamps: tuple[pd.Timestamp, ...]
    gap_blocks: tuple[GapBlock, ...]
    is_trading_session: bool
    is_scheduled_early_close: bool
    opening_range_complete: bool
    usable_for_orb: bool
    unusable_reason: str | None


def get_calendar():
    return xcals.get_calendar("XNYS")


def _session_label(trading_date: date | str | pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(trading_date).normalize()


@lru_cache(maxsize=None)
def is_trading_session(trading_date: date | str | pd.Timestamp) -> bool:
    return bool(get_calendar().is_session(_session_label(trading_date)))


@lru_cache(maxsize=None)
def get_expected_market_open(trading_date: date | str | pd.Timestamp) -> pd.Timestamp | None:
    label = _session_label(trading_date)
    calendar = get_calendar()
    if not calendar.is_session(label):
        return None
    return calendar.session_open(label).tz_convert(NEW_YORK_TZ)


@lru_cache(maxsize=None)
def get_expected_market_close(trading_date: date | str | pd.Timestamp) -> pd.Timestamp | None:
    label = _session_label(trading_date)
    calendar = get_calendar()
    if not calendar.is_session(label):
        return None
    return calendar.session_close(label).tz_convert(NEW_YORK_TZ)


@lru_cache(maxsize=None)
def get_expected_regular_session_minutes(
    trading_date: date | str | pd.Timestamp,
) -> pd.DatetimeIndex:
    label = _session_label(trading_date)
    calendar = get_calendar()
    if not calendar.is_session(label):
        return pd.DatetimeIndex([], tz=NEW_YORK_TZ)
    return calendar.session_minutes(label).tz_convert(NEW_YORK_TZ)


@lru_cache(maxsize=None)
def is_scheduled_early_close(trading_date: date | str | pd.Timestamp) -> bool:
    minutes = get_expected_regular_session_minutes(trading_date)
    if minutes.empty:
        return False
    return len(minutes) < 390


def get_session_type(trading_date: date | str | pd.Timestamp) -> SessionQuality:
    if not is_trading_session(trading_date):
        return SessionQuality.NO_SESSION
    if is_scheduled_early_close(trading_date):
        return SessionQuality.SCHEDULED_EARLY_CLOSE
    return SessionQuality.COMPLETE


def _to_ny_minute_index(timestamps: Iterable[pd.Timestamp]) -> pd.DatetimeIndex:
    raw_values = list(timestamps)
    if not raw_values:
        return pd.DatetimeIndex([], tz=NEW_YORK_TZ)

    for value in raw_values:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")

    values = pd.DatetimeIndex(pd.to_datetime(raw_values, utc=True))
    return values.tz_convert(NEW_YORK_TZ).floor("min").drop_duplicates().sort_values()


def _gap_blocks(missing: pd.DatetimeIndex) -> tuple[GapBlock, ...]:
    if missing.empty:
        return ()
    blocks: list[GapBlock] = []
    start = prev = missing[0]
    for current in missing[1:]:
        if current - prev == pd.Timedelta(minutes=1):
            prev = current
            continue
        blocks.append(GapBlock(start=start, end=prev, minutes=int((prev - start) / pd.Timedelta(minutes=1)) + 1))
        start = prev = current
    blocks.append(GapBlock(start=start, end=prev, minutes=int((prev - start) / pd.Timedelta(minutes=1)) + 1))
    return tuple(blocks)


def compare_session_minutes(
    trading_date: date | str | pd.Timestamp,
    actual_timestamps: Iterable[pd.Timestamp],
    *,
    large_gap_min_minutes: int | None = None,
) -> SessionQualityReport:
    label = _session_label(trading_date)
    session_date = label.date()
    expected_minutes = get_expected_regular_session_minutes(label)
    actual_minutes = _to_ny_minute_index(actual_timestamps)

    if expected_minutes.empty:
        first = actual_minutes[0] if len(actual_minutes) else None
        last = actual_minutes[-1] if len(actual_minutes) else None
        return SessionQualityReport(
            trading_date=session_date,
            quality=SessionQuality.NO_SESSION,
            expected_open=None,
            expected_close=None,
            expected_bar_count=0,
            actual_bar_count=len(actual_minutes),
            missing_bar_count=0,
            unexpected_extra_count=len(actual_minutes),
            first_actual_bar=first,
            last_actual_bar=last,
            missing_timestamps=(),
            unexpected_extra_timestamps=tuple(actual_minutes),
            gap_blocks=(),
            is_trading_session=False,
            is_scheduled_early_close=False,
            opening_range_complete=False,
            usable_for_orb=False,
            unusable_reason="NO_SESSION",
        )

    expected_set = set(expected_minutes)
    actual_set = set(actual_minutes)
    missing = pd.DatetimeIndex(sorted(expected_set - actual_set))
    extras = pd.DatetimeIndex(sorted(actual_set - expected_set))
    blocks = _gap_blocks(missing)
    scheduled_early_close = len(expected_minutes) < 390
    first = actual_minutes[0] if len(actual_minutes) else None
    last = actual_minutes[-1] if len(actual_minutes) else None

    opening_expected = tuple(
        ts for ts in expected_minutes if ts.time() in OPENING_RANGE_TIMES
    )
    opening_range_complete = bool(opening_expected) and all(
        ts in actual_set for ts in opening_expected
    )

    structural_large_gap = bool(blocks) and (
        len(actual_minutes.intersection(expected_minutes)) == 0
        or any(
            block.minutes > 1
            and (block.start == expected_minutes[0] or block.end == expected_minutes[-1])
            for block in blocks
        )
    )

    if missing.empty:
        quality = SessionQuality.SCHEDULED_EARLY_CLOSE if scheduled_early_close else SessionQuality.COMPLETE
    elif structural_large_gap:
        quality = SessionQuality.LARGE_DATA_GAP
    elif large_gap_min_minutes is not None and any(block.minutes >= large_gap_min_minutes for block in blocks):
        quality = SessionQuality.LARGE_DATA_GAP
    else:
        quality = SessionQuality.DATA_GAP

    unusable_reason = None
    usable_for_orb = quality in {SessionQuality.COMPLETE, SessionQuality.SCHEDULED_EARLY_CLOSE} and opening_range_complete
    if not opening_range_complete:
        unusable_reason = "MISSING_OPENING_RANGE_MINUTE"
    elif quality == SessionQuality.DATA_GAP:
        unusable_reason = "DATA_GAP"
    elif quality == SessionQuality.LARGE_DATA_GAP:
        unusable_reason = "LARGE_DATA_GAP"
    elif quality == SessionQuality.NO_SESSION:
        unusable_reason = "NO_SESSION"

    return SessionQualityReport(
        trading_date=session_date,
        quality=quality,
        expected_open=expected_minutes[0],
        expected_close=expected_minutes[-1] + pd.Timedelta(minutes=1),
        expected_bar_count=len(expected_minutes),
        actual_bar_count=len(actual_minutes.intersection(expected_minutes)),
        missing_bar_count=len(missing),
        unexpected_extra_count=len(extras),
        first_actual_bar=first,
        last_actual_bar=last,
        missing_timestamps=tuple(missing),
        unexpected_extra_timestamps=tuple(extras),
        gap_blocks=blocks,
        is_trading_session=True,
        is_scheduled_early_close=scheduled_early_close,
        opening_range_complete=opening_range_complete,
        usable_for_orb=usable_for_orb,
        unusable_reason=unusable_reason,
    )
