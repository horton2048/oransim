"""Niche registry — single source of truth for niche keys, Chinese labels,
synonyms, and CTR priors.

Loads from ``data/niches.json`` at import time (overridable via the env var
``ORAN_NICHES_PATH``). All modules that used to hard-code small EN→ZH maps or
8-niche lists pull from helpers here instead, so adding a new niche is one
edit to the JSON registry.

Example — point at your own registry:

    ORAN_NICHES_PATH=/srv/my_niches.json python -m uvicorn oransim.api:app

The shipped JSON covers the 10 niches in ``data/synthetic/notes_v3.json`` so
the default demo runs coherent. Replace it with your own niches (keeping the
schema) when you wire in a real ``DataProvider``.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "niches.json"


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    path = Path(os.environ.get("ORAN_NICHES_PATH") or _DEFAULT_PATH)
    with open(path, encoding="utf-8") as f:
        return json.load(f)["niches"]


def reload() -> None:
    """Bust the lru cache. Tests / admin-hot-reload flows can call this."""
    _load.cache_clear()


def niches() -> list[dict]:
    """Full list of niche dicts (key / zh / en / synonyms / ctr_prior / ...)."""
    return _load()


def niche_keys() -> list[str]:
    """Ordered list of EN keys — used by kol library + model training."""
    return [n["key"] for n in _load()]


def niche_zh_list() -> list[str]:
    """Ordered list of Chinese display labels."""
    return [n["zh"] for n in _load()]


def en_to_zh() -> dict[str, str]:
    """EN key → Chinese display label (the map that used to be repeated in
    soul.py / schema_outputs.py / predict.py / kol_optimizer.py ...)."""
    return {n["key"]: n["zh"] for n in _load()}


def zh_to_en() -> dict[str, str]:
    """Chinese label → EN key (reverse map, for caption-detect fallbacks)."""
    return {n["zh"]: n["key"] for n in _load()}


def synonyms() -> dict[str, list[str]]:
    """EN key → list of keyword/brand synonyms used for caption→niche match."""
    return {n["key"]: list(n.get("synonyms", [])) for n in _load()}


def ctr_priors() -> dict[str, dict[str, float]]:
    """EN key → {mu, sigma, n} industry CTR priors (for CTR fallback / display)."""
    return {n["key"]: dict(n["ctr_prior"]) for n in _load()}


def bias_captions() -> dict[str, str]:
    """EN key → short caption used by mock KOL embedding (kols.py NICHE_BIAS_CAPTIONS)."""
    return {n["key"]: n.get("bias_caption", n["zh"]) for n in _load()}


def female_ratio() -> dict[str, int]:
    """EN key → approximate female fan ratio (for mock KOL demographics)."""
    return {n["key"]: int(n.get("female_ratio", 50)) for n in _load()}


# Default reference prices per niche (CNY). Used when niches.json lacks 'reference_price'.
# Aligned with CATEGORY_DEFAULTS in spec/extract.py (kept in sync manually).
_REFERENCE_PRICE_FALLBACK: dict[str, float] = {
    "beauty":      89.0,
    "food":        25.0,
    "fitness":    199.0,
    "fashion":    159.0,
    "electronics": 399.0,
    "pet":         59.0,
    "travel":     299.0,
    "baby":       129.0,
    "education":  199.0,
    "home":        89.0,
    "general":     45.0,
}


# 默认采纳率先验 (Bass m 标定用). niches.json 无 adoption_rate_prior (v2 字段, M8 补)
# 前用这组逐 niche 区分的回退值; 不同 niche 不同 → 市场潜量 m 不同 (AT-M5-06).
_ADOPTION_RATE_FALLBACK: dict[str, float] = {
    "beauty":      0.080,
    "fashion":     0.060,
    "food":        0.120,
    "beverage":    0.130,
    "fitness":     0.055,
    "electronics": 0.045,
    "travel":      0.040,
    "home":        0.050,
    "pet":         0.070,
    "parenting":   0.065,
    "general":     0.060,
}


def adoption_rate_priors() -> tuple[dict[str, float], set[str]]:
    """EN key → 采纳率先验 (Bass 市场潜量标定) + 未标定 niche 集合.

    返回 (rates, uncalibrated). niches.json 缺 adoption_rate_prior 字段的 niche
    用回退值并入 uncalibrated (报告需显式标「未标定」)。
    """
    rates: dict[str, float] = {}
    uncalibrated: set[str] = set()
    for n in _load():
        key = n["key"]
        if "adoption_rate_prior" in n:
            rates[key] = float(n["adoption_rate_prior"])
        else:
            rates[key] = _ADOPTION_RATE_FALLBACK.get(key, 0.06)
            uncalibrated.add(key)
    return rates, uncalibrated


def adoption_rate_prior(niche: str) -> float:
    """单 niche 采纳率先验 (缺省回退 0.06)。"""
    rates, _ = adoption_rate_priors()
    return rates.get(niche, _ADOPTION_RATE_FALLBACK.get(niche, 0.06))


def reference_prices() -> tuple[dict[str, float], set[str]]:
    """EN key → reference price CNY + set of uncalibrated (default) niches.

    Returns (prices_dict, uncalibrated_set). Niches in uncalibrated_set used a
    fallback default (niches.json lacked a 'reference_price' field — 未标定).
    """
    prices: dict[str, float] = {}
    uncalibrated: set[str] = set()
    for n in _load():
        key = n["key"]
        if "reference_price" in n:
            prices[key] = float(n["reference_price"])
        else:
            prices[key] = _REFERENCE_PRICE_FALLBACK.get(key, 45.0)
            uncalibrated.add(key)
    return prices, uncalibrated
