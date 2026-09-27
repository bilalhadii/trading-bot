from paper_trading.config import PaperTradingConfig


def test_paper_trading_config_defaults_are_conservative():
    config = PaperTradingConfig()

    assert config.strategy_version == "ORB_RETEST_RECLAIM_BODY_2R"
    assert config.target_r == 2.0
    assert config.risk_fraction == 0.0025
    assert config.max_trade_risk_fraction == 0.0025
    assert config.max_notional_fraction == 0.25
    assert config.max_daily_loss_fraction == 0.01
    assert config.allow_short_selling


def test_paper_trading_config_builds_risk_limits():
    limits = PaperTradingConfig(
        risk_fraction=0.001,
        max_trade_risk_fraction=0.001,
        max_notional_fraction=0.1,
        max_daily_loss_fraction=0.005,
        allow_short_selling=False,
    ).risk_limits()

    assert limits.max_trade_risk_fraction == 0.001
    assert limits.max_notional_fraction == 0.1
    assert limits.max_daily_loss_fraction == 0.005
    assert not limits.allow_short_selling
