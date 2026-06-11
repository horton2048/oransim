"""agents/launch_outputs.py — LaunchReport 组装 (方案 §7, 规范 §10).

四区块全部派生自现有机器:
  头部   — 假设回显 + 三色来源标注 + grounding_confidence
  区块1  — 指标 (上市词表 + P35/P50/P65 分位带, P35 标「下行情形」)
  区块2  — 90 天时间线 (peak_day / half_life / saturation_date)
  区块3  — 谁会买 (CATE 分群 + persona 引语)
  区块4  — 什么会出问题 (干预叙事卡 + audit_risk + 季节窗口)

文案红线 (规范 §10, AT-M7-12):
  - 报告第一句逐字「这是带标注不确定性的情景推演，不是预测」
  - P35 行带「下行情形」
  - 竞品卡固定前缀 (COMPETITOR_BRANCH_PREFIX)
  - objection 原话逐字, 不润色
  - locale != zh-CN → assumed_fields 含「市场环境按中国社媒市场模拟」

依赖方向: agents 是引擎层, 禁止依赖 spec 包 (REG-4)。spec 对象由调用方
(api_routers/launch.py) 以 model_dump() 字典传入, 本模块只收 dict。
"""
from __future__ import annotations

from typing import Any

# 报告第一句 (逐字红线)
FIRST_SENTENCE = "这是带标注不确定性的情景推演，不是预测"
# 非中国 locale 的市场环境标注 (逐字红线)
NON_ZH_LOCALE_NOTE = "市场环境按中国社媒市场模拟"
# P35 下行情形标注
DOWNSIDE_LABEL = "下行情形"

_QUANTILES = (0.35, 0.50, 0.65)


def _empirical_quantile(values: list[float], q: float) -> float:
    """经验分位数 (线性插值)。values 已无需排序由本函数排。"""
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return float(xs[lo] * (1 - frac) + xs[hi] * frac)


def _quant_band(values: list[float], *, single: bool) -> dict[str, Any]:
    """构造一个指标的 P35/P50/P65 分位带; single=True 时无带 + 标注。"""
    if single or len(values) <= 1:
        v = float(values[0]) if values else 0.0
        return {"p50": v, "band": None, "note": "单点、无分位带"}
    return {
        "p35": _empirical_quantile(values, 0.35),
        "p50": _empirical_quantile(values, 0.50),
        "p65": _empirical_quantile(values, 0.65),
        "p35_label": DOWNSIDE_LABEL,
        "band": True,
    }


def _source_tag(spec_dict: dict, field_name: str, assumed_fields: list[str]) -> str:
    """三色来源标注: 用户原话 / LLM 推断 / 系统默认。"""
    if field_name in assumed_fields:
        # assumed = inferred 或 default_applied
        fields_meta = spec_dict.get("fields", {})
        fmeta = fields_meta.get(field_name, {})
        if fmeta.get("default_applied"):
            return "系统默认"
        return "LLM 推断"
    # provenance 非空 → 用户原话/已确认
    if spec_dict.get("provenance"):
        return "用户原话"
    return "LLM 推断"


def build_launch_report(
    *,
    spec_dict: dict,
    assumed_fields: list[str],
    grounding: dict,
    per_seed_kpis: list[dict],
    launch_personas: list[dict],
    timeline: dict,
    cate_segments: list[dict],
    intervention_cards: list[dict],
    audit_risk: float,
    season_window: dict,
    locale: str = "zh-CN",
    budget_hint_cny: float | None = None,
) -> dict:
    """组装完整 LaunchReport (dict)。per_seed_kpis = 多 seed run 的 total_kpis 列表。"""
    n_seeds = len(per_seed_kpis)
    single = n_seeds <= 1

    # locale 标注 (红线): 非 zh-CN 在 assumed_fields 注明
    af = list(assumed_fields)
    if locale != "zh-CN" and NON_ZH_LOCALE_NOTE not in af:
        af.append(NON_ZH_LOCALE_NOTE)

    grounding_confidence = float(grounding.get("grounding_confidence", 0.0))

    # ---- 头部: 假设回显 + 三色来源 ----
    spec_fields = ["product_name", "one_liner", "category_raw", "target_user_raw",
                   "price_point", "channels_hint"]
    header = {
        "disclaimer": FIRST_SENTENCE,
        "grounding_confidence": grounding_confidence,
        "assumptions": [
            {
                "field": f,
                "value": spec_dict.get(f),
                "source": _source_tag(spec_dict, f, assumed_fields),
            }
            for f in spec_fields
        ],
    }

    # ---- 区块1: 指标 (上市词表 + 分位带) ----
    def _metric(values: list[float]) -> dict:
        return _quant_band(values, single=single)

    reach_vals = [k.get("impressions", 0.0) for k in per_seed_kpis]
    click_vals = [k.get("clicks", 0.0) for k in per_seed_kpis]
    adopter_vals = [k.get("conversions", 0.0) for k in per_seed_kpis]
    revenue_vals = [k.get("revenue", 0.0) for k in per_seed_kpis]
    cost_vals = [k.get("cost", 0.0) for k in per_seed_kpis]
    adoption_rate_vals = [
        (k.get("conversions", 0.0) / k.get("impressions", 1.0)) if k.get("impressions") else 0.0
        for k in per_seed_kpis
    ]
    # payback: revenue / budget_hint (相对 budget_hint 的回本)
    bh = budget_hint_cny or (cost_vals[0] if cost_vals else 1.0) or 1.0
    payback_vals = [r / bh for r in revenue_vals]

    metrics = {
        "unique_reach": _metric(reach_vals),
        "trials": _metric(click_vals),
        "adopters": _metric(adopter_vals),
        "adoption_rate": _metric(adoption_rate_vals),
        "revenue": _metric(revenue_vals),
        "payback": _metric(payback_vals),
        "n_seeds": n_seeds,
        "quantile_source": "ScenarioRunner 多 seed Monte Carlo 经验分位数",
    }
    if single:
        metrics["degradation_note"] = "单点、无分位带"

    # ---- 区块3: 谁会买 (CATE 分群 + persona 引语; objection 原话不润色) ----
    persona_quotes = [
        {
            "will_try": p.get("will_try"),
            "would_pay_cny": p.get("would_pay_cny"),
            "objection": p.get("objection", ""),   # 原话逐字
            "purchase_intent_7d": p.get("purchase_intent_7d"),
        }
        for p in launch_personas
    ]
    who_buys = {
        "cate_segments": cate_segments,
        "persona_quotes": persona_quotes,
        "objections_as_risk": [q["objection"] for q in persona_quotes if q["objection"]],
    }

    # ---- 区块4: 什么会出问题 (干预卡 + audit_risk + 季节窗口) ----
    what_breaks = {
        "intervention_cards": intervention_cards,
        "audit_risk": float(audit_risk),
        "season_window": season_window,
    }

    return {
        # 顶层诚实标记 (红线: 每个 launch 响应都有)
        "assumed_fields": af,
        "grounding_confidence": grounding_confidence,
        "disclaimer": FIRST_SENTENCE,
        "header": header,
        "metrics": metrics,
        "timeline": timeline,
        "who_buys": who_buys,
        "what_breaks": what_breaks,
        "locale": locale,
    }
