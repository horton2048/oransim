"""spec/route.py — 分诊台: ground 信号 → 可信度档位 (A/B/C). 永不硬拒.

老产品是「保安」: ground() 对 B2B / 低置信 / 非消费硬拒, 直接对用户报「测不了」。
本模块在**产品编排层**把「拒绝」改为「路由」—— ground() 的诚实判定 (rejected /
niche / confidence) 一律保留, 仅用来决定走哪一档, 不再对用户 dead-end (proposal
BREAKING; design D-1)。

档位规则 (design D-1 / tasks 1.2):
  - ground.rejected (b2b / 低置信 / 非消费)            → C  (LLM 情景推演, 无伪精确 KPI)
  - 未拒 & niche 有 fan_prior 校准 (含别名)            → A  (校准模拟: 分位带+时间线+证词)
  - 未拒 & niche 无 fan_prior                           → B  (同 A 管线但标「未校准」、拉宽区间)

niche→fan_prior 别名表是 A/B 的边界。fan_profile.NICHE_PRIORS 的英文 key 是
beauty/mom/tech/food/fashion/fitness/finance/travel(+calibrated home)，而 ground
产出的是 niches.json 的 10 个 CN 消费 key (beauty/fashion/food/beverage/fitness/
electronics/travel/home/pet/parenting)。两套命名不一致, 故此处显式维护映射:
electronics→tech、parenting→mom 命中校准 prior 判 A; beverage/home/pet 及 M8 v2
品类无对应 prior 判 B (design 明列 home→B, 即使 calibrated 里恰好有 home——分诊
保守, 宁可 B 兜底也不假装精确)。
"""
from __future__ import annotations

from .ground import GroundingResult

# niches.json niche_key → fan_profile prior key。**有映射 = 校准垂类 = A 档**。
# 无映射的消费 niche (beverage/home/pet/v2) 落 B 档。
_NICHE_TO_PRIOR: dict[str, str] = {
    "beauty": "beauty",
    "fashion": "fashion",
    "food": "food",
    "fitness": "fitness",
    "travel": "travel",
    "electronics": "tech",   # 别名: 数码 → tech 校准 prior
    "parenting": "mom",      # 别名: 母婴/育儿 → mom 校准 prior
}

TIER_LABELS: dict[str, str] = {
    "A": "A · 校准模拟",
    "B": "B · 未校准结构化",
    "C": "C · AI 情景推演",
}

# C 端友好的「这一档有多可信」一句话 (honest-prediction-labeling: 可信度是卖点)
TIER_BLURB: dict[str, str] = {
    "A": "有校准语料的消费垂类——精确分位带、90 天时间线、真实模拟用户证词。",
    "B": "消费品但缺校准语料——同一套推演，但读数仅供参考、区间已放宽。",
    "C": "引擎演不了的领域（B2B / 线下服务 / 全新物种）——只给定性情景，不给伪精确数字。",
}


def route_idea(g: GroundingResult) -> str:
    """ground 结果 → 档位 'A' | 'B' | 'C'。永不返回「拒绝」。

    同一 idea → 同一 ground → 同一档位 (可复现; ground 关键词命中确定性优先)。
    """
    if g.rejected:
        return "C"
    if g.niche_key in _NICHE_TO_PRIOR:
        return "A"
    return "B"


def resolve_prior_niche(g: GroundingResult) -> str | None:
    """A 档: 把 ground 的 niche_key 解析成实际校准 prior key (electronics→tech)。

    供 `_simulate_sync` 的 `market_potential` / `fan_profile_summary` 用——否则
    用原始 "electronics" 查 NICHE_PRIORS 落空 → 退化成 base-population, A 档就名不
    副实 (号称校准实则未校准)。B/C 档返回 None (B 用原 niche 走 base-pop)。
    """
    if g.rejected:
        return None
    return _NICHE_TO_PRIOR.get(g.niche_key or "")


def routed_reason(g: GroundingResult, tier: str) -> str:
    """给前端展示的「为什么分到这一档」一句话 (诚实标注: 让用户看懂分诊逻辑)。"""
    if tier == "C":
        why = {
            "b2b": "B2B / 企业软件——引擎无校准语料",
            "unsupported_vertical": "非消费垂类或接地置信不足",
        }.get(g.reject_reason or "", "引擎无校准语料")
        return f"{why}，分诊台不再硬拒，路由到 C 档定性推演"
    if tier == "B":
        return f"识别为消费品「{g.niche_key}」但无校准 fan_prior，走结构化推演并标「未校准」"
    return f"命中校准垂类「{g.niche_key}」，走全结构化校准模拟"
