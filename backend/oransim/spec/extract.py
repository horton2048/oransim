"""spec/extract.py — LLM 抽取 (双模式) + CATEGORY_DEFAULTS 默认表.

LLM_MODE=mock: 关键词匹配 + 品类默认预算/价格表, 零网络出站, CI 确定性.
LLM_MODE=api : call_llm_json_with_retry() + provenance span, 结构化 JSON.
规范 §3.2.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from .schema import ProductSpec, SpecField

# ---------------------------------------------------------------------------
# CATEGORY_DEFAULTS — 品类默认预算/价格表 (default_applied=True 来源)
# ---------------------------------------------------------------------------

CATEGORY_DEFAULTS: dict[str, dict[str, Any]] = {
    "beauty":       {"price_cny": 89.0,  "budget_cny": 50_000.0, "channels": ["xiaohongshu", "douyin"]},
    "food":         {"price_cny": 25.0,  "budget_cny": 30_000.0, "channels": ["douyin", "xiaohongshu"]},
    "fitness":      {"price_cny": 199.0, "budget_cny": 60_000.0, "channels": ["xiaohongshu", "douyin"]},
    "fashion":      {"price_cny": 159.0, "budget_cny": 80_000.0, "channels": ["xiaohongshu", "tiktok"]},
    "electronics":  {"price_cny": 399.0, "budget_cny": 100_000.0, "channels": ["douyin", "jd"]},
    "pet":          {"price_cny": 59.0,  "budget_cny": 40_000.0, "channels": ["xiaohongshu"]},
    "travel":       {"price_cny": 299.0, "budget_cny": 70_000.0, "channels": ["xiaohongshu", "douyin"]},
    "baby":         {"price_cny": 129.0, "budget_cny": 50_000.0, "channels": ["xiaohongshu"]},
    "education":    {"price_cny": 199.0, "budget_cny": 40_000.0, "channels": ["xiaohongshu", "weixin"]},
    "home":         {"price_cny": 89.0,  "budget_cny": 30_000.0, "channels": ["xiaohongshu", "douyin"]},
    "general":      {"price_cny": 99.0,  "budget_cny": 50_000.0, "channels": ["xiaohongshu", "douyin"]},
}

# ---------------------------------------------------------------------------
# Mock extraction — keyword-based, deterministic, zero LLM cost
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(r"[¥￥]?\s*(\d+(?:\.\d+)?)\s*(?:元|RMB|CNY|块|¥)?")
_CHANNEL_KW: dict[str, str] = {
    "小红书": "xiaohongshu", "xhs": "xiaohongshu",
    "抖音": "douyin", "tiktok": "douyin",
    "微信": "weixin", "wechat": "weixin",
    "淘宝": "taobao", "天猫": "tmall", "京东": "jd",
    "bilibili": "bilibili", "b站": "bilibili",
    "微博": "weibo",
}

_NICHE_SYNONYMS: dict[str, list[str]] = {}  # lazy-loaded


def _niche_synonyms() -> dict[str, list[str]]:
    global _NICHE_SYNONYMS
    if not _NICHE_SYNONYMS:
        try:
            from oransim.config import niches as _n
            _NICHE_SYNONYMS = _n.synonyms()
        except Exception:
            pass
    return _NICHE_SYNONYMS


def _detect_category(text: str) -> tuple[str, str]:
    """Return (niche_key, category_raw). Keyword match first, fallback 'general'."""
    text_lower = text.lower()
    syn = _niche_synonyms()
    for niche, kws in syn.items():
        if any(k.lower() in text_lower for k in kws):
            return niche, kws[0] if kws else niche
    # Chinese keyword fallback
    _CH: dict[str, str] = {
        "美妆": "beauty", "口红": "beauty", "粉底": "beauty", "护肤": "beauty",
        "食品": "food", "饮料": "food", "零食": "food", "奶": "food", "茶": "food",
        "健身": "fitness", "运动": "fitness", "蛋白": "fitness",
        "服装": "fashion", "穿搭": "fashion", "手机壳": "electronics",
        "数码": "electronics", "耳机": "electronics", "宠物": "pet",
        "旅行": "travel", "旅游": "travel", "母婴": "baby", "教育": "education",
        "家居": "home", "家具": "home",
    }
    for kw, cat in _CH.items():
        if kw in text:
            return cat, kw
    return "general", text[:20]


def _extract_channels(text: str) -> list[str]:
    result = []
    tl = text.lower()
    for kw, ch in _CHANNEL_KW.items():
        if kw.lower() in tl and ch not in result:
            result.append(ch)
    return result


def _extract_price(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if m:
        return float(m.group(1))
    return None


def _idea_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def _mock_extract(idea_text: str) -> ProductSpec:
    """Deterministic extraction via keyword matching + CATEGORY_DEFAULTS."""
    niche_key, cat_raw = _detect_category(idea_text)
    defaults = CATEGORY_DEFAULTS.get(niche_key, CATEGORY_DEFAULTS["general"])

    extracted_price = _extract_price(idea_text)
    price_cny = extracted_price if extracted_price is not None else defaults["price_cny"]
    price_has_provenance = extracted_price is not None

    extracted_channels = _extract_channels(idea_text)
    channels = extracted_channels if extracted_channels else defaults["channels"]
    channels_has_provenance = bool(extracted_channels)

    # Build per-field metadata
    fields: dict[str, SpecField] = {
        "budget_default": SpecField(
            value=str(defaults["budget_cny"]),
            inferred=False,
            default_applied=True,
            provenance=[],
        ),
    }
    if not price_has_provenance:
        fields["price_default"] = SpecField(
            value=str(price_cny),
            inferred=False,
            default_applied=True,
            provenance=[],
        )
    if not channels_has_provenance:
        fields["channels_default"] = SpecField(
            value=str(channels),
            inferred=False,
            default_applied=True,
            provenance=[],
        )

    # Top-level provenance: we have at least the text itself
    top_provenance = [{"start": 0, "end": len(idea_text)}]

    return ProductSpec(
        product_name=idea_text[:40].strip(),
        one_liner=idea_text[:80].strip(),
        category_raw=cat_raw,
        target_user_raw="",
        price_point={"amount": price_cny, "currency": "CNY", "model": "one_time"},
        differentiation=[],
        substitutes_raw=[],
        channels_hint=channels,
        value_props=[],
        confidence=0.6,
        provenance=top_provenance,
        inferred=False,
        default_applied=False,
        fields=fields,
    )


# ---------------------------------------------------------------------------
# LLM extraction (api mode)
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """You are a product analyst. Extract the following structured info from the user's idea text.
Return JSON with keys:
product_name, one_liner, category_raw, target_user_raw,
price_point (object: amount float, currency str, model one_time|subscription|freemium),
differentiation (list[str]), substitutes_raw (list[str]),
channels_hint (list[str]), value_props (list[str]).

For each field you extract, if you can cite a span of the original text, include provenance.
If you must infer something not stated, set inferred=true for that field.
If no price mentioned, use amount=0."""


def _llm_extract(idea_text: str) -> ProductSpec:
    from oransim.agents.soul_llm import call_llm_json_with_retry, llm_available
    if not llm_available():
        return _mock_extract(idea_text)

    model = os.environ.get("LLM_MODEL", "gpt-5.4")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _EXTRACT_PROMPT},
            {"role": "user", "content": idea_text},
        ],
        "temperature": 0,
    }
    try:
        parsed, _ = call_llm_json_with_retry(body)
    except Exception:
        return _mock_extract(idea_text)

    # 部分模型 (如 agnes) 会把字段返回成 {"value":..., "provenance":...} 对象 (我们的
    # prompt 允许带 provenance)。统一解包成标量, 否则 str(dict) 会把整坨字典塞进字段。
    def _sval(x, default=""):
        if isinstance(x, dict):
            x = x.get("value", x.get("text", default))
        return default if x is None else str(x)

    def _slist(x):
        out = []
        for it in (x or []):
            v = it.get("value", it.get("text")) if isinstance(it, dict) else it
            if v is not None and str(v).strip():
                out.append(str(v))
        return out

    pp = parsed.get("price_point", {})
    if isinstance(pp, dict) and "value" in pp and not any(k in pp for k in ("amount", "currency", "model")):
        pp = pp["value"] if isinstance(pp["value"], dict) else {"amount": pp["value"]}
    if not pp or not isinstance(pp, dict):
        pp = {"amount": 0.0, "currency": "CNY", "model": "one_time"}

    def _amt(v):
        try:
            return float(str(_sval(v, "0")).replace("¥", "").replace("元", "").strip() or 0)
        except Exception:
            return 0.0

    return ProductSpec(
        product_name=_sval(parsed.get("product_name"), idea_text[:40]),
        one_liner=_sval(parsed.get("one_liner"), idea_text[:80]),
        category_raw=_sval(parsed.get("category_raw"), ""),
        target_user_raw=_sval(parsed.get("target_user_raw"), ""),
        price_point={
            "amount": _amt(pp.get("amount", 0.0)),
            "currency": _sval(pp.get("currency"), "CNY"),
            "model": _sval(pp.get("model"), "one_time"),
        },
        differentiation=_slist(parsed.get("differentiation")),
        substitutes_raw=_slist(parsed.get("substitutes_raw")),
        channels_hint=_slist(parsed.get("channels_hint")),
        value_props=_slist(parsed.get("value_props")),
        confidence=0.75,
        provenance=[{"start": 0, "end": len(idea_text)}],
        inferred=False,
        default_applied=False,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_spec(idea_text: str) -> ProductSpec:
    """Extract ProductSpec from free-text idea (dual mode: mock or LLM)."""
    mode = os.environ.get("LLM_MODE", "mock")
    if mode == "mock":
        return _mock_extract(idea_text)
    return _llm_extract(idea_text)
