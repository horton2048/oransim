"""spec/normalize.py — 纯 Python 规整, 无 LLM.

职责: 币种→CNY, 价格夹紧, 枚举强制, raw 字段逐字保留.
规范 §3.3.
"""

from __future__ import annotations

from .schema import ProductSpec

# Simple FX table (mock; production would call forex API)
_FX_TO_CNY: dict[str, float] = {
    "CNY": 1.0,
    "USD": 7.25,
    "EUR": 7.85,
    "HKD": 0.93,
    "GBP": 9.10,
    "JPY": 0.048,
}

_VALID_PRICE_MODELS = {"one_time", "subscription", "freemium"}
_DEFAULT_PRICE_MODEL = "one_time"

# Price clamp: 0.01 CNY – 1,000,000 CNY
_MIN_PRICE_CNY = 0.01
_MAX_PRICE_CNY = 1_000_000.0


def normalize_spec(spec: ProductSpec) -> ProductSpec:
    """Return a new ProductSpec with normalized price_point.

    Invariants:
    - category_raw, target_user_raw, substitutes_raw are preserved verbatim.
    - price_point.currency → CNY; amount multiplied by FX rate.
    - price_point.model clamped to valid enum or set to default.
    - price_point.amount clamped to [_MIN_PRICE_CNY, _MAX_PRICE_CNY].
    """
    pp = dict(spec.price_point)

    # currency → CNY
    ccy = str(pp.get("currency", "CNY")).upper()
    fx = _FX_TO_CNY.get(ccy, 1.0)
    amount = float(pp.get("amount", 0.0))
    pp["amount"] = max(_MIN_PRICE_CNY, min(_MAX_PRICE_CNY, amount * fx))
    pp["currency"] = "CNY"

    # pricing model: force to valid enum
    model = str(pp.get("model", _DEFAULT_PRICE_MODEL))
    if model not in _VALID_PRICE_MODELS:
        pp["model"] = _DEFAULT_PRICE_MODEL

    data = spec.model_dump()
    data["price_point"] = pp
    return ProductSpec(**data)
