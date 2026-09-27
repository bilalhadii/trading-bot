from dataclasses import dataclass

from paper_trading.risk import RiskLimits


@dataclass(frozen=True)
class PaperTradingConfig:
    strategy_version: str = "ORB_RETEST_RECLAIM_BODY_2R"
    target_r: float = 2.0
    risk_fraction: float = 0.0025
    max_trade_risk_fraction: float = 0.0025
    max_notional_fraction: float = 0.25
    max_daily_loss_fraction: float = 0.01
    allow_short_selling: bool = True

    def risk_limits(self) -> RiskLimits:
        return RiskLimits(
            max_trade_risk_fraction=self.max_trade_risk_fraction,
            max_notional_fraction=self.max_notional_fraction,
            max_daily_loss_fraction=self.max_daily_loss_fraction,
            allow_short_selling=self.allow_short_selling,
        )
