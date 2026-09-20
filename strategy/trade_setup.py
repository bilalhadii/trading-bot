from typing import Optional


def calculate_trade_setup(
    direction: str,
    entry: float,
    or_high: float,
    or_low: float,
    pdh: Optional[float],
    pdl: Optional[float],
    minimum_rr: float = 2.0,
) -> Optional[dict]:
    """
    Create a basic ORB trade setup.

    LONG:
        Stop   = OR Low
        Target = PDH

    SHORT:
        Stop   = OR High
        Target = PDL

    A setup is rejected if:
        - Required PDH/PDL is unavailable
        - Target is on the wrong side of entry
        - Risk <= 0
        - R:R is below minimum_rr
    """

    direction = direction.upper()

    if direction not in {"LONG", "SHORT"}:
        raise ValueError(
            f"Invalid direction: {direction}"
        )

    if direction == "LONG":

        if pdh is None:
            return None

        stop = float(or_low)
        target = float(pdh)

        risk = entry - stop
        reward = target - entry

    else:

        if pdl is None:
            return None

        stop = float(or_high)
        target = float(pdl)

        risk = stop - entry
        reward = entry - target

    if risk <= 0:
        return None

    if reward <= 0:
        return None

    rr = reward / risk

    if rr < minimum_rr:
        return None

    return {
        "direction": direction,
        "entry": float(entry),
        "stop": stop,
        "target": target,
        "risk": risk,
        "reward": reward,
        "risk_reward": rr,
        "pdh": pdh,
        "pdl": pdl,
        "or_high": or_high,
        "or_low": or_low,
    }