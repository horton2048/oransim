"""agents/launch_scenario_llm.py — C 档 LLM 情景推演 (design D-2, tasks §2).

引擎演不了的想法 (B2B / 线下服务 / 全新物种) **不进 Bass / world-model**, 由真
LLM 出定性情景: 市场盘子 (数量级超宽区间) / 买家画像 / 渠道适配 / 采纳曲线形状 /
关键风险。

红线 (honest-prediction-labeling):
  - C 档**不产任何点值 KPI 分位带** (no_kpi=True)；一切量级逐字标「数量级估计，非校准」。
  - 视觉与 A 档强区分由前端保证；后端保证字段诚实 (无 reach/adopters/revenue 分位带)。
  - LLM 不可用 / 解析失败 → **显式降级** (degraded=True + 提示), 绝不静默造占位情景。

REG-4: agents 是引擎层, 不 import spec 包。spec 以 model_dump() dict 传入 (同
build_launch_report)。LLM 走 soul_llm 的同一 provider 注册表 (mock 模式 / 桩 provider
均可经 get_provider 接管 → 测试可注入)。
"""

from __future__ import annotations

import re
import time
from typing import Any

from .launch_outputs import FIRST_SENTENCE, _source_tag
from .llm_providers import get_provider
from .soul_llm import MODEL, _extract_json_strict, llm_available

TIER_BADGE_C = "C · AI 情景推演 · 未校准"
NO_KPI_NOTE = (
    "C 档不产精确 KPI：没有 reach/trials/adopters/revenue 的分位带。"
    "下方一切量级均为数量级估计，逐字标注「非校准」。"
)
# LLM 不可用时的诚实降级文案 (不静默造占位 — design D-2)
DEGRADE_NOTE = (
    "C 档情景推演需要真 LLM (LLM_MODE=api 且密钥就绪)。当前 LLM 不可用，"
    "故未生成情景——按红线不静默编造占位内容。"
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

_SYSTEM = """你是消费品 / 产业新品上市的情景推演分析师。
面对一个「引擎无校准语料」的想法（常见于 B2B、线下服务、全新物种），你只做**定性**研判，
绝不编造精确数字。你给出的任何市场量级都必须是「数量级估计」，且用超宽区间表达「测不准」。
只输出严格 JSON，不要任何额外解释、不要代码块围栏。"""

_PROMPT = """对下面这个产品想法做一份**定性情景推演**（不是精确预测）。

产品想法：{idea}
（系统识别：{category} / 目标用户：{target} / 接地判定：{reason}）

严格输出 JSON，字段如下（市场盘子只给数量级与超宽区间，不要精确数字；采纳形状只描述曲线形状与拐点逻辑，不给逐日数字）：
{{
  "market_sizing": {{
    "range_low": <可服务市场 SAM 的下界, 纯整数 CNY/年, 取数量级粗估>,
    "range_high": <上界, 应≥下界一个数量级左右, 纯整数>,
    "unit": "CNY / 年（可服务市场 SAM）",
    "basis": "一句话说明这个量级怎么粗估出来的（哪几项相乘）"
  }},
  "buyer_personas": [
    {{"who": "谁（角色/身份）", "jobs_to_be_done": "他要解决什么", "willingness": "付费意愿与顾虑", "objection": "用他自己的话写一句最大异议（20字内，不润色）"}}
  ],
  "channels": [
    {{"channel": "渠道名", "fit": "适配度评级 + 一句理由（高/中/低）"}}
  ],
  "adoption_shape": {{
    "shape": "用一个短语概括曲线形状（如：长导入期 + 滞后陡峭 S 曲线）",
    "narrative": "2-3 句叙述采纳为什么是这个形状、拐点由什么决定（不要任何逐日数字）"
  }},
  "key_risks": ["风险1", "风险2", "风险3", "风险4"]
}}

要求：buyer_personas 给 2-3 个，channels 给 3-4 个，key_risks 给 4-5 条。"""


def _strip_think(s: str) -> str:
    return _THINK_RE.sub("", s or "").strip()


def _build_header(spec_dict: dict, assumed_fields: list[str]) -> dict:
    """C 档头部: 与 A 档同款三色来源标注 (honest labeling 一致性)。"""
    spec_fields = [
        "product_name",
        "one_liner",
        "category_raw",
        "target_user_raw",
        "price_point",
        "channels_hint",
    ]
    return {
        "disclaimer": FIRST_SENTENCE,
        "tier_badge": TIER_BADGE_C,
        "assumptions": [
            {
                "field": f,
                "value": spec_dict.get(f),
                "source": _source_tag(spec_dict, f, assumed_fields),
            }
            for f in spec_fields
        ],
    }


def _normalize_scenario(raw: dict) -> dict:
    """把 LLM 原始 JSON 规范成 C 档情景契约 (盖红线标记: magnitude_only / no_numbers)。

    market_sizing 强制 range_low<=range_high; 若 LLM 给了过窄区间 (不足约 3×),
    不悄悄改数值, 但保留 interval_note 提醒「这是有意的超宽区间」。
    """
    ms = raw.get("market_sizing") or {}
    lo = _to_int(ms.get("range_low"))
    hi = _to_int(ms.get("range_high"))
    if lo is not None and hi is not None and hi < lo:
        lo, hi = hi, lo
    market_sizing = {
        "label": "市场盘子（数量级估计，非校准）",
        "magnitude_only": True,
        "range_low": lo,
        "range_high": hi,
        "unit": str(ms.get("unit") or "CNY / 年（可服务市场 SAM）"),
        "interval_note": "跨约一个数量级——这是有意的超宽区间，反映「测不准」而非精确",
        "basis": str(ms.get("basis") or "LLM 定性估计，粗估三项相乘"),
    }

    personas = []
    for p in (raw.get("buyer_personas") or [])[:4]:
        if not isinstance(p, dict):
            continue
        personas.append(
            {
                "who": str(p.get("who") or "").strip(),
                "jobs_to_be_done": str(p.get("jobs_to_be_done") or "").strip(),
                "willingness": str(p.get("willingness") or "").strip(),
                "objection": str(p.get("objection") or "").strip(),  # 逐字不润色
            }
        )

    channels = []
    for c in (raw.get("channels") or [])[:6]:
        if not isinstance(c, dict):
            continue
        channels.append(
            {
                "channel": str(c.get("channel") or "").strip(),
                "fit": str(c.get("fit") or "").strip(),
            }
        )

    ash = raw.get("adoption_shape") or {}
    adoption_shape = {
        "shape": str(ash.get("shape") or "").strip(),
        "no_numbers": True,
        "narrative": str(ash.get("narrative") or "").strip(),
        "contrast_with_A": "与 A 档「90 天日采纳曲线」不同：C 档不给逐日数字，只给曲线形状与拐点逻辑",
    }

    key_risks = [str(r).strip() for r in (raw.get("key_risks") or []) if str(r).strip()][:6]

    return {
        "market_sizing": market_sizing,
        "buyer_personas": personas,
        "channels": channels,
        "adoption_shape": adoption_shape,
        "key_risks": key_risks,
        "confidence_note": (
            "以上全部为 LLM 定性推演，无任何校准数据支撑。把它当作「该往哪些方向做尽调」"
            "的起点，不是「会发生什么」的预测。"
        ),
    }


def _to_int(v: Any) -> int | None:
    try:
        return int(float(str(v).replace(",", "").replace("¥", "").strip()))
    except Exception:
        return None


def _envelope(
    *,
    spec_dict,
    assumed_fields,
    routed_reason,
    grounding_confidence,
    scenario,
    degraded,
    degrade_note=None,
    _meta=None,
) -> dict:
    """统一 C 档响应信封 (design D-3)。degraded=True 时 scenario=None + 提示。"""
    env = {
        "tier": "C",
        "tier_label": "C · LLM 情景推演",
        "disclaimer": FIRST_SENTENCE,
        "uncalibrated": True,
        "no_kpi": True,
        "no_kpi_note": NO_KPI_NOTE,
        "grounding_confidence": grounding_confidence,  # C 档常为 None/低
        "routed_reason": routed_reason,
        "assumed_fields": list(assumed_fields),
        "header": _build_header(spec_dict, assumed_fields),
        "scenario": scenario,
        "degraded": degraded,
    }
    if degraded:
        env["degrade_note"] = degrade_note or DEGRADE_NOTE
    if _meta:
        env["_llm_meta"] = _meta
    return env


def build_scenario_report(
    *,
    spec_dict: dict,
    idea_text: str,
    routed_reason: str,
    assumed_fields: list[str],
    grounding_confidence: float | None = None,
    locale: str = "zh-CN",
) -> dict:
    """C 档主入口: idea → LLM → 定性情景信封。

    LLM 不可用 / 解析失败 → degraded 信封 (scenario=None), 不静默造占位。
    """
    af = list(assumed_fields)
    note = "无校准语料 → 全部为 LLM 定性估计"
    if note not in af:
        af.append(note)

    if not llm_available():
        return _envelope(
            spec_dict=spec_dict,
            assumed_fields=af,
            routed_reason=routed_reason,
            grounding_confidence=grounding_confidence,
            scenario=None,
            degraded=True,
        )

    prompt = _PROMPT.format(
        idea=idea_text or spec_dict.get("one_liner") or spec_dict.get("product_name") or "",
        category=spec_dict.get("category_raw") or "未识别",
        target=spec_dict.get("target_user_raw") or "未识别",
        reason=routed_reason,
    )
    t0 = time.time()
    try:
        result = get_provider().generate(
            system=_SYSTEM,
            user=prompt,
            model=MODEL,
            temperature=0.7,
            max_tokens=900,
            stream=False,
        )
        raw = _extract_json_strict(_strip_think(result.content))
        scenario = _normalize_scenario(raw)
        meta = {
            "latency_ms": getattr(result, "latency_ms", None) or int((time.time() - t0) * 1000),
            "tokens_in": int((getattr(result, "usage", {}) or {}).get("prompt_tokens", 0) or 0),
            "tokens_out": int(
                (getattr(result, "usage", {}) or {}).get("completion_tokens", 0) or 0
            ),
        }
        return _envelope(
            spec_dict=spec_dict,
            assumed_fields=af,
            routed_reason=routed_reason,
            grounding_confidence=grounding_confidence,
            scenario=scenario,
            degraded=False,
            _meta=meta,
        )
    except Exception as e:  # noqa: BLE001 — 解析/网络失败 → 显式降级, 不造占位
        env = _envelope(
            spec_dict=spec_dict,
            assumed_fields=af,
            routed_reason=routed_reason,
            grounding_confidence=grounding_confidence,
            scenario=None,
            degraded=True,
            degrade_note=f"C 档 LLM 情景生成失败（{type(e).__name__}）——按红线不静默编造占位。",
        )
        return env
