"""spec/scenario_gen.py — 编译 ProductSpec 为 Scenario + 合成 creative + 种子事件.

职责 (方案 §3.5):
  - 合成发布 creative: 每平台 1–3 条, 全走 data/creatives.make_creative()
    (64 维 content_emb、audit_risk、category_hint 原封生效).
  - 渠道分配: channels_hint 优先; 无 hint → 按 niche 默认渠道先验 (进 assumed).
  - KOL 种子: data/kols.pick_kol_by_spec() 按品类选达人.
  - 预算默认: 价格点 + ctr_priors() 推导, 进 assumed_fields (default_applied).
  - Hawkes 种子事件: 上市日曝光脉冲, 规模 = budget_to_impressions() 折算.

依赖方向: spec/ → engine. 引擎层不反向 import (REG-4).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from oransim.config import niches as _niches
from oransim.data.creatives import Creative, make_creative
from oransim.data.kols import KOL, pick_kol_by_spec
from oransim.data.platforms import budget_to_impressions
from oransim.platforms.xhs.world_model_legacy import AudienceFilter

from .schema import ProductSpec

# 合法上市平台 = 世界模型 PLATFORM_NAMES ∩ data/platforms.PLATFORMS (两边都识别,
# 既能跑 simulate_impression 又能 budget_to_impressions). wechat_video 无 cpm,
# tiktok 不在 world model, 故排除.
_LAUNCH_PLATFORMS = ("douyin", "xhs", "bilibili", "kuaishou")
_DEFAULT_PLATFORM = "xhs"

# 渠道 hint (extract 产出的英文/中文渠道名) → 世界模型平台名
_CHANNEL_TO_PLATFORM: dict[str, str] = {
    "xiaohongshu": "xhs", "xhs": "xhs", "小红书": "xhs",
    "douyin": "douyin", "tiktok": "douyin", "抖音": "douyin",
    "bilibili": "bilibili", "b站": "bilibili", "哔哩": "bilibili",
    "kuaishou": "kuaishou", "快手": "kuaishou",
    # 无诚实世界模型平台的渠道 → 映射到最近社媒代理
    "weixin": "douyin", "wechat": "douyin", "微信": "douyin",
    "jd": "xhs", "taobao": "xhs", "tmall": "xhs", "京东": "xhs", "weibo": "xhs",
}

# 按 niche 的默认渠道先验 (无 channels_hint 时用). 与 extract.CATEGORY_DEFAULTS 同源理念.
_NICHE_DEFAULT_CHANNELS: dict[str, list[str]] = {
    "beauty": ["xhs", "douyin"], "fashion": ["xhs", "douyin"],
    "food": ["douyin", "xhs"], "beverage": ["douyin", "xhs"],
    "fitness": ["xhs", "douyin"], "electronics": ["douyin", "bilibili"],
    "travel": ["xhs", "douyin"], "home": ["xhs", "douyin"],
    "pet": ["xhs"], "parenting": ["xhs"],
}

_PRICE_MODEL_DEFAULT = "one_time"


@dataclass
class CompiledScenario:
    """编译五元组 (方案 §3.5) + assumed_fields 诚实标记."""
    spec: ProductSpec
    scenario: object                       # causal.counterfactual.Scenario
    launch_creatives: dict[str, list[Creative]]
    seed_events: dict[str, float]          # platform → 上市日种子脉冲规模
    clarification_questions: list[str] = field(default_factory=list)
    assumed_fields: list[str] = field(default_factory=list)


def _spec_fingerprint(spec: ProductSpec) -> str:
    """spec 内容指纹 (不含易变元数据), 用于确定性 creative id."""
    basis = "|".join([
        spec.product_name, spec.category_raw, spec.target_user_raw,
        str(spec.price_point.get("amount")), ",".join(spec.channels_hint),
    ])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:10]


def _resolve_platforms(spec: ProductSpec) -> tuple[list[str], bool]:
    """返回 (platforms, defaulted). channels_hint 优先, 无则用 niche 先验.

    defaulted=True 表示渠道来自默认先验 (spec.fields 标了 channels_default 或
    channels_hint 为空) → 上层据此把 platform_alloc 记入 assumed_fields.
    """
    channels_defaulted = "channels_default" in spec.fields
    hint = [c for c in (spec.channels_hint or []) if c]
    if hint and not channels_defaulted:
        platforms = []
        for c in hint:
            p = _CHANNEL_TO_PLATFORM.get(c.lower(), _DEFAULT_PLATFORM)
            if p not in platforms:
                platforms.append(p)
        return (platforms or [_DEFAULT_PLATFORM]), False

    # 默认先验: 按 niche
    niche = _infer_niche(spec)
    chans = _NICHE_DEFAULT_CHANNELS.get(niche, [_DEFAULT_PLATFORM])
    platforms = []
    for p in chans:
        if p not in platforms:
            platforms.append(p)
    return platforms, True


def _infer_niche(spec: ProductSpec) -> str:
    """轻量 niche 推断 (scenario_gen 内部用, grounding 在 ground.py)。"""
    text = f"{spec.category_raw} {spec.one_liner}".lower()
    syn = _niches.synonyms()
    for niche in _niches.niche_keys():
        for kw in syn.get(niche, []):
            if kw and kw.lower() in text:
                return niche
    return "beauty"


def _platform_alloc(platforms: list[str]) -> dict[str, float]:
    """等权分配, 归一化到合计 1.0。"""
    valid = [p for p in platforms if p in _LAUNCH_PLATFORMS] or [_DEFAULT_PLATFORM]
    w = 1.0 / len(valid)
    return {p: w for p in valid}


def _derive_budget(spec: ProductSpec, niche: str) -> float:
    """无 budget_hint 时由价格点 + ctr_priors 推导默认预算 (确定性)。

    思路: 目标触达一批潜在买家. CTR 越低需越多曝光 → 预算越高. 用 niche 的
    ctr_prior.mu 与价格点做线性折算, 夹紧到合理区间。
    """
    priors = _niches.ctr_priors()
    mu = float(priors.get(niche, {}).get("mu", 0.04)) or 0.04
    price = float(spec.price_point.get("amount", 50.0)) or 50.0
    # 目标: ~2000 次点击的曝光预算等价; budget ∝ price / ctr 的有界折算
    budget = 50_000.0 * (0.04 / mu) * (1.0 + min(price, 1000.0) / 1000.0) / 2.0
    return float(max(10_000.0, min(200_000.0, round(budget, 2))))


def _make_audience_filter(spec: ProductSpec) -> AudienceFilter:
    """从 spec 文本派生软定向 (关键词 boost)。intern 由 pipeline 负责。"""
    kws = []
    if spec.target_user_raw:
        kws.append(spec.target_user_raw)
    if spec.category_raw:
        kws.append(spec.category_raw)
    return AudienceFilter(interest_keywords=kws or None, boost_strength=2.0)


def _synth_creatives(spec: ProductSpec, niche: str, platform: str, fp: str) -> list[Creative]:
    """每平台合成 1–3 条发布 creative, 全走 make_creative (mock: bias_caption 模板)。"""
    caps = _niches.bias_captions()
    base_cap = caps.get(niche, niche)
    name = spec.product_name or spec.category_raw or "新品"
    templates = [
        f"{name}｜{base_cap} 上市种草",
        f"{name} 测评｜{spec.one_liner[:24]}",
        f"{name}｜{base_cap} 好物推荐",
    ]
    # 平台数量决定条数: 单平台给 2 条, 多平台各 1–2 条 (确定性按 fp+platform)。
    n = 1 + (int(hashlib.sha256(f"{fp}:{platform}".encode()).hexdigest()[:2], 16) % 3)  # 1..3
    creatives = []
    for i in range(n):
        cid = f"lc_{fp}_{platform}_{i}"
        cre = make_creative(creative_id=cid, caption=templates[i % len(templates)],
                            duration_sec=15.0)
        creatives.append(cre)
    return creatives


def compile_scenario(
    spec: ProductSpec,
    *,
    audience_filter: AudienceFilter,
    kols: list[KOL] | None = None,
    budget_hint_cny: float | None = None,
    seed: int = 0,
) -> CompiledScenario:
    """把 ProductSpec 编译为可直通 ScenarioRunner.run() 的 Scenario + 配套产物.

    audience_filter 由调用方 (pipeline) intern 后传入, 保证同 spec 版本同实例。
    """
    from oransim.causal.counterfactual import Scenario

    assumed: list[str] = list(spec.assumed_fields)
    niche = _infer_niche(spec)
    fp = _spec_fingerprint(spec)

    # 1. 渠道 → platform_alloc
    platforms, alloc_defaulted = _resolve_platforms(spec)
    platform_alloc = _platform_alloc(platforms)
    if alloc_defaulted and "platform_alloc" not in assumed:
        assumed.append("platform_alloc")

    # 2. 预算
    if budget_hint_cny is not None:
        total_budget = float(budget_hint_cny)
    else:
        total_budget = _derive_budget(spec, niche)
        if "total_budget" not in assumed:
            assumed.append("total_budget")

    # 3. 合成 creative (每平台 1–3 条)
    launch_creatives = {p: _synth_creatives(spec, niche, p, fp) for p in platform_alloc}
    primary = next(iter(launch_creatives.values()))[0]  # Scenario 单 creative: 取首条

    # 4. KOL 种子
    kol_per_platform = None
    if kols:
        kol_per_platform = {
            p: pick_kol_by_spec(kols, p, niche=niche) for p in platform_alloc
        }
        kol_per_platform = {p: k for p, k in kol_per_platform.items() if k is not None}

    # 5. Scenario (price/pricing_model/substitute_pressure 默认 None — 行为不变)
    scenario = Scenario(
        creative=primary,
        total_budget=total_budget,
        platform_alloc=platform_alloc,
        audience_filter=audience_filter,
        kol_per_platform=kol_per_platform or None,
        seed=seed,
    )

    # 6. Hawkes 种子事件: 上市日曝光脉冲 = budget_to_impressions 折算
    seed_events = {
        p: budget_to_impressions(total_budget * frac, p)
        for p, frac in platform_alloc.items()
    }

    return CompiledScenario(
        spec=spec,
        scenario=scenario,
        launch_creatives=launch_creatives,
        seed_events=seed_events,
        clarification_questions=[],
        assumed_fields=assumed,
    )
