import pytest

from scripts.execute_approved_trade import calculate_target


def test_calculate_target_long():
    assert calculate_target(
        direction="LONG",
        entry=100.0,
        stop=98.0,
        target_r=2.0,
    ) == 104.0


def test_calculate_target_short():
    assert calculate_target(
        direction="SHORT",
        entry=100.0,
        stop=102.0,
        target_r=2.0,
    ) == 96.0


def test_calculate_target_rejects_invalid_long_risk():
    with pytest.raises(ValueError, match="LONG stop"):
        calculate_target(
            direction="LONG",
            entry=100.0,
            stop=101.0,
            target_r=2.0,
        )
