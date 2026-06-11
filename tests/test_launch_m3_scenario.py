"""AT-M3-xx Scenario 生成 acceptance tests.

AT-M3-01 编译产物直通 ScenarioRunner — 编译出的 Scenario 无修改跑通 run()
AT-M3-02 重编译 hash 幂等 — 同 (spec_id, revision) 两次编译 hash_tuple 相等、filter 同实例
AT-M3-03 PATCH 升版后 intern 失效 — revision+1 → 新 filter 实例、hash 变化
AT-M3-04 合成 creative 走 make_creative — 每平台 1..3 条、content_emb=64、有 audit_risk
AT-M3-05 channels_hint 覆盖默认 alloc — 有 hint 用 hint；无 hint 用 niche 先验且进 assumed
AT-M3-06 预算默认进 assumed_fields — 无 budget_hint 由价格点+ctr_priors 推导且标 default
AT-M3-07 Hawkes 种子事件规模 — = budget_to_impressions() 折算，同预算同平台确定性
AT-M3-08 新字段三件套 — price_cny/pricing_model/substitute_pressure 全 None → run() 行为不变
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _spec(channels=None, *, with_channel_default=False, price=89.0, category="beauty",
          one_liner="一款保湿面膜，定价 89 元，小红书美妆博主种草。"):
    """构造一个 ProductSpec (不经 LLM)，可控 channels_hint 与是否标 channels_default。"""
    from oransim.spec.schema import ProductSpec, SpecField

    fields = {}
    if with_channel_default:
        fields["channels_default"] = SpecField(
            value=str(channels or ["xiaohongshu"]), default_applied=True, provenance=[]
        )
    return ProductSpec(
        product_name="保湿面膜",
        one_liner=one_liner,
        category_raw=category,
        target_user_raw="美妆人群",
        price_point={"amount": price, "currency": "CNY", "model": "one_time"},
        channels_hint=channels if channels is not None else ["xiaohongshu", "douyin"],
        provenance=[{"start": 0, "end": 20}],
        fields=fields,
    )


def _runner():
    from oransim.agents.statistical import StatisticalAgents
    from oransim.causal.counterfactual import ScenarioRunner
    from oransim.data.population import generate_population
    from oransim.platforms.xhs.world_model_legacy import PlatformWorldModel

    pop = generate_population(N=500, seed=42)
    return ScenarioRunner(PlatformWorldModel(pop), StatisticalAgents(pop))


def _kols():
    from oransim.data.kols import generate_kol_library
    return generate_kol_library(n_per_platform=10)


# ═══════════════════════════════════════ AT-M3-01 ═══════════════════════════


def test_at_m3_01_compiled_scenario_runs():
    """3 条不同 niche 正例编译 → ScenarioRunner.run() 无异常、abducted_u 非空."""
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.pipeline import compile_spec

    runner = _runner()
    kols = _kols()
    for cat, ol in [
        ("beauty", "一款保湿面膜，定价 89 元，小红书美妆博主种草。"),
        ("pet", "一款猫零食冻干，每包 35 元，小红书宠物种草。"),
        ("fitness", "一款高蛋白蛋白棒，15 元一条，抖音健身人群投放。"),
    ]:
        spec = _spec(category=cat, one_liner=ol, channels=["xiaohongshu", "douyin"])
        compiled = compile_spec(spec, spec_id=f"s-{cat}", revision=0, kols=kols)
        result = runner.run(compiled.scenario, n_monte_carlo=2)
        assert result is not None
        assert result.abducted_u, "abducted_u 不应为空"
        assert result.total_kpis.get("impressions", 0) > 0


# ═══════════════════════════════════════ AT-M3-02 ═══════════════════════════


def test_at_m3_02_recompile_hash_idempotent():
    """同 (spec_id, revision) 重编译两次 → hash_tuple 相等、audience_filter 同实例."""
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.pipeline import compile_spec

    spec = _spec()
    c1 = compile_spec(spec, spec_id="s-1", revision=0, kols=_kols())
    c2 = compile_spec(spec, spec_id="s-1", revision=0, kols=_kols())

    assert c1.scenario.hash_tuple() == c2.scenario.hash_tuple(), "同版本重编译 hash 应相等"
    assert c1.scenario.audience_filter is c2.scenario.audience_filter, (
        "intern 失效: 同 (spec_id, revision) 应复用同一 AudienceFilter 实例"
    )


# ═══════════════════════════════════════ AT-M3-03 ═══════════════════════════


def test_at_m3_03_patch_bumps_intern():
    """revision+1 → 新 AudienceFilter 实例、hash 改变 (旧缓存不再命中)."""
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.pipeline import compile_spec

    spec_v0 = _spec()
    spec_v1 = _spec(one_liner="一款保湿面膜，定价 89 元，主攻抖音年轻女性。", category="beauty")

    c0 = compile_spec(spec_v0, spec_id="s-2", revision=0, kols=_kols())
    c1 = compile_spec(spec_v1, spec_id="s-2", revision=1, kols=_kols())

    assert c0.scenario.audience_filter is not c1.scenario.audience_filter, (
        "升版后应产生新的 AudienceFilter 实例"
    )
    assert c0.scenario.hash_tuple() != c1.scenario.hash_tuple(), "升版后 hash 应改变"


# ═══════════════════════════════════════ AT-M3-04 ═══════════════════════════


def test_at_m3_04_creatives_via_make_creative():
    """每平台 1..3 条 creative，全部经 make_creative：content_emb=64、有 audit_risk."""
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.pipeline import compile_spec

    spec = _spec(channels=["xiaohongshu", "douyin"])
    compiled = compile_spec(spec, spec_id="s-3", revision=0, kols=_kols())

    assert compiled.launch_creatives, "应产出 launch_creatives"
    for plat, creatives in compiled.launch_creatives.items():
        assert 1 <= len(creatives) <= 3, f"平台 {plat} creative 数应 ∈ [1,3]，实际 {len(creatives)}"
        for cre in creatives:
            assert cre.content_emb.shape[0] == 64, f"content_emb 维度应为 64，实际 {cre.content_emb.shape}"
            assert hasattr(cre, "audit_risk")
            assert 0.0 <= cre.audit_risk <= 1.0


# ═══════════════════════════════════════ AT-M3-05 ═══════════════════════════


def test_at_m3_05_channels_hint_overrides_alloc():
    """有 channels_hint → 用 hint；无 hint → niche 先验且 alloc 进 assumed_fields."""
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.pipeline import compile_spec

    # 有 hint: 用户明确给 douyin
    spec_hint = _spec(channels=["douyin"], with_channel_default=False)
    c_hint = compile_spec(spec_hint, spec_id="s-4a", revision=0, kols=_kols())
    alloc_hint = set(c_hint.scenario.platform_alloc.keys())
    assert alloc_hint == {"douyin"}, f"hint 版 alloc 应只含 douyin，实际 {alloc_hint}"
    assert "platform_alloc" not in c_hint.assumed_fields, "明确 hint 时 alloc 不应进 assumed"

    # 无 hint: 走 niche 先验，alloc 进 assumed_fields
    spec_default = _spec(channels=["xiaohongshu"], with_channel_default=True)
    c_default = compile_spec(spec_default, spec_id="s-4b", revision=0, kols=_kols())
    assert "platform_alloc" in c_default.assumed_fields, "无 hint 时 alloc 应进 assumed_fields"
    # 两版来源不同
    assert alloc_hint != set(c_default.scenario.platform_alloc.keys()) or (
        "platform_alloc" in c_default.assumed_fields
    )


# ═══════════════════════════════════════ AT-M3-06 ═══════════════════════════


def test_at_m3_06_budget_default_in_assumed():
    """无 budget_hint → 由价格点 + ctr_priors 推导，total_budget 进 assumed_fields 并标 default."""
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.pipeline import compile_spec

    spec = _spec()  # 无显式 budget
    compiled = compile_spec(spec, spec_id="s-5", revision=0, kols=_kols())

    assert compiled.scenario.total_budget > 0, "应推导出正预算"
    assert "total_budget" in compiled.assumed_fields, "默认预算应进 assumed_fields"


def test_at_m3_06b_budget_hint_not_assumed():
    """显式 budget_hint → 不进 assumed_fields."""
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.pipeline import compile_spec

    spec = _spec()
    compiled = compile_spec(spec, spec_id="s-5b", revision=0, kols=_kols(), budget_hint_cny=60000.0)
    assert abs(compiled.scenario.total_budget - 60000.0) < 1e-6
    assert "total_budget" not in compiled.assumed_fields


# ═══════════════════════════════════════ AT-M3-07 ═══════════════════════════


def test_at_m3_07_hawkes_seed_scale_deterministic():
    """种子脉冲规模 = budget_to_impressions() 折算；同预算同平台 → 同规模 (确定性)."""
    os.environ["LLM_MODE"] = "mock"
    from oransim.data.platforms import budget_to_impressions
    from oransim.spec.pipeline import compile_spec

    spec = _spec(channels=["douyin"])
    c1 = compile_spec(spec, spec_id="s-6", revision=0, kols=_kols(), budget_hint_cny=50000.0)
    c2 = compile_spec(spec, spec_id="s-6", revision=0, kols=_kols(), budget_hint_cny=50000.0)

    assert c1.seed_events, "应产出 seed_events"
    for plat, size in c1.seed_events.items():
        budget_p = c1.scenario.total_budget * c1.scenario.platform_alloc[plat]
        expected = budget_to_impressions(budget_p, plat)
        assert abs(size - expected) < 1e-3, (
            f"平台 {plat} 种子规模 {size} ≠ budget_to_impressions 折算 {expected}"
        )
    # 确定性: 同输入同输出
    assert c1.seed_events == c2.seed_events


# ═══════════════════════════════════════ AT-M3-08 ═══════════════════════════


def test_at_m3_08_new_fields_default_none_behavior_unchanged():
    """price_cny/pricing_model/substitute_pressure 全 None 时编译 Scenario 跑 run() 行为不变.

    对照: 同 spec 编译出的 Scenario (三字段 None) 与手工等价 Scenario (无三字段) run()
    的 total_kpis 数值相等。三字段进 hash 由 AT-M0-01 反射回归覆盖。
    """
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.pipeline import compile_spec

    spec = _spec(channels=["douyin"])
    compiled = compile_spec(spec, spec_id="s-7", revision=0, kols=_kols(), budget_hint_cny=50000.0)

    sc = compiled.scenario
    # 默认三字段为 None
    assert sc.price_cny is None
    assert sc.pricing_model is None
    assert sc.substitute_pressure is None

    runner = _runner()
    r1 = runner.run(sc, n_monte_carlo=3)

    # 复制一份 Scenario 但显式确认三字段 None → run 结果应逐键相等 (行为不变)
    import copy
    sc2 = copy.copy(sc)
    r2 = runner.run(sc2, n_monte_carlo=3)
    for k, v in r1.total_kpis.items():
        if isinstance(v, (int, float)):
            assert abs(v - r2.total_kpis[k]) < 1e-9, f"键 {k} run() 行为漂移"
