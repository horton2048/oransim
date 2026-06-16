"""AT-M4-xx 价格端到端 acceptance tests.

AT-M4-01: AOV 参数化后 predict 快照不变 — aggregate_kpis(price_cny=None) 路径 = 旧行为
AT-M4-02: price=None 数值等价 — aggregate_kpis(price_cny=None) vs 45.0 hardcoded 数值相等
AT-M4-03: 价格特征自然退化 — price_cny=None/ref → feat=0 → convert_prob 与基线一致；2×ref → 不同
AT-M4-04: 价格单调性 — sandbox price +30% → conversions 下降；-30% → 上升
AT-M4-05: 价格×预算交换律 — 先价格后预算 vs 先预算后价格 最终 revenue 相等（rel_tol=1e-6）
AT-M4-06: price elif 用当前 conversions — revenue = 当前 session conversions × 新价
AT-M4-07: reference_price getter — reference_prices() 返回 dict；缺 reference_price 字段时有默认
AT-M4-08: 决策权重冻结 — W_CLICK/W_ENGAGE/W_CONVERT 数值与改造前一致；只允许新增价格项系数
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────── helpers ────────────────────────────


def _make_pop(n: int = 200):
    from oransim.data.population import Population

    rng = np.random.default_rng(42)
    pop = Population.__new__(Population)
    pop.n = n
    pop.bigfive = rng.random((n, 5)).astype(np.float32)
    pop.state = rng.random((n, 16)).astype(np.float32)
    pop.age_idx = rng.integers(0, 5, n).astype(np.int32)
    pop.income = rng.random(n).astype(np.float32) * 9.0
    pop.gender = rng.integers(0, 2, n).astype(np.int32)
    return pop


def _make_creative(cid: str = "m4-test"):
    from oransim.data.creatives import make_creative

    return make_creative(creative_id=cid, caption="m4 price test", duration_sec=15.0)


def _make_impression(pop, k: int = 50):
    from oransim.platforms.xhs.world_model_legacy import ImpressionResult

    rng = np.random.default_rng(7)
    idx = rng.choice(pop.n, size=k, replace=False).astype(np.int32)
    return ImpressionResult(
        platform="douyin",
        agent_idx=idx,
        total_impressions=k * 10,
        score_breakdown={
            "content": np.full(k, 0.5, dtype=np.float32),
            "platform_activity": np.full(k, 0.6, dtype=np.float32),
            "audience_filter": np.full(k, 0.7, dtype=np.float32),
            "kol_boost": np.full(k, 0.3, dtype=np.float32),
        },
        weight=np.ones(k, dtype=np.float32),
    )


def _make_agents(pop):
    from oransim.agents.statistical import StatisticalAgents

    return StatisticalAgents(pop)


def _make_scenario(**overrides):
    from oransim.causal.counterfactual import Scenario
    from oransim.data.creatives import make_creative

    base = dict(
        creative=make_creative(creative_id="m4-sc", caption="m4 scenario", duration_sec=15.0),
        total_budget=5_000.0,
        platform_alloc={"douyin": 1.0},
        seed=42,
    )
    base.update(overrides)
    return Scenario(**base)


def _make_sandbox():
    """Minimal SandboxStore backed by a lightweight ScenarioRunner (no api_state bootstrap)."""
    from oransim.agents.statistical import StatisticalAgents
    from oransim.causal.counterfactual import ScenarioRunner
    from oransim.data.population import generate_population
    from oransim.platforms.xhs.world_model_legacy import PlatformWorldModel
    from oransim.sandbox.engine import SandboxStore

    pop = generate_population(N=500, seed=42)
    wm = PlatformWorldModel(pop)
    ag = StatisticalAgents(pop)
    runner = ScenarioRunner(wm, ag)
    return SandboxStore(runner)


# ═══════════════════════════════════════ AT-M4-01 ═══════════════════════════


def test_at_m4_01_aov_param_snapshot_unchanged():
    """aggregate_kpis(price_cny=None) 与旧行为（conv_value_cny=45.0）字节级等价.

    覆盖铁律 1：price=None 路径不改变 REG-2 快照字节。
    实现层断言：调用新签名 price_cny=None 产出 revenue 与旧签名 45.0 数值相等。
    （REG-2 byte-level check 已由 AT-M0-02 持续覆盖，此处作函数层验证层叠。）
    """

    pop = _make_pop()
    ag = _make_agents(pop)
    imp = _make_impression(pop)
    creative = _make_creative()
    oc = ag.simulate(imp, creative, rng_seed=0)

    budget = 5_000.0
    # 新签名：price_cny=None → 内部回退 45.0
    kpi_new = ag.aggregate_kpis(oc, imp, budget, price_cny=None)
    # 旧签名兼容性：旧 conv_value_cny 已更名，用 45.0 显式对照
    revenue_expected = float(np.sum(oc.convert_prob * imp.weight)) * 45.0
    assert math.isclose(
        kpi_new["revenue"], revenue_expected, rel_tol=1e-7
    ), f"price_cny=None 下 revenue {kpi_new['revenue']} ≠ expected {revenue_expected}"
    assert math.isclose(kpi_new["cost"], budget, rel_tol=1e-9)


# ═══════════════════════════════════════ AT-M4-02 ═══════════════════════════


def test_at_m4_02_price_none_numeric_equiv():
    """aggregate_kpis(price_cny=None) 与旧实现（45.0 硬编码）全部键数值完全相等."""

    pop = _make_pop()
    ag = _make_agents(pop)
    imp = _make_impression(pop)
    creative = _make_creative()
    oc = ag.simulate(imp, creative, rng_seed=1)
    budget = 8_000.0

    kpi_none = ag.aggregate_kpis(oc, imp, budget, price_cny=None)

    # 旧实现期望值（45.0 固化在测试内）
    conversions = float(np.sum(oc.convert_prob * imp.weight))
    clicks = float(np.sum(oc.click_prob * imp.weight))
    imps = float(imp.total_impressions)
    revenue_expected = conversions * 45.0
    roi_expected = (revenue_expected - budget) / max(budget, 1)
    ctr_expected = clicks / max(imps, 1)
    cvr_expected = conversions / max(clicks, 1)

    assert math.isclose(kpi_none["revenue"], revenue_expected, rel_tol=1e-7)
    assert math.isclose(kpi_none["roi"], roi_expected, rel_tol=1e-7)
    assert math.isclose(kpi_none["ctr"], ctr_expected, rel_tol=1e-7)
    assert math.isclose(kpi_none["cvr"], cvr_expected, rel_tol=1e-7)
    assert math.isclose(kpi_none["cost"], budget, rel_tol=1e-9)
    assert math.isclose(kpi_none["conversions"], conversions, rel_tol=1e-7)
    assert math.isclose(kpi_none["clicks"], clicks, rel_tol=1e-7)


# ═══════════════════════════════════════ AT-M4-03 ═══════════════════════════


def test_at_m4_03_price_feature_natural_degradation():
    """price_cny=None 或 price_cny==reference_price 时价格特征为 0（log(1)=0）.

    三组对照（None / 等于参考价 / 2倍参考价）固定 seed 跑 simulate：
    - 前两组 convert_prob 逐 agent 相等（价格特征 = 0，不影响 logit）。
    - 第三组 convert_prob 不等（价格特征 = log(2) ≠ 0）。
    """

    pop = _make_pop()
    ag = _make_agents(pop)
    imp = _make_impression(pop)
    creative = _make_creative()
    ref_price = 45.0  # 内置参考价（spec §7.1 默认值）

    oc_none = ag.simulate(imp, creative, rng_seed=5, price_cny=None)
    oc_ref = ag.simulate(imp, creative, rng_seed=5, price_cny=ref_price, reference_price=ref_price)
    oc_2x = ag.simulate(
        imp, creative, rng_seed=5, price_cny=ref_price * 2, reference_price=ref_price
    )

    # None 与 reference 等价：逐 agent convert_prob 相等
    np.testing.assert_array_almost_equal(
        oc_none.convert_prob,
        oc_ref.convert_prob,
        decimal=8,
        err_msg="price_cny=None 与 price_cny=reference_price 的 convert_prob 应相等",
    )

    # 2× reference 产生不同（更低）convert_prob
    assert not np.allclose(
        oc_none.convert_prob, oc_2x.convert_prob
    ), "price_cny=2×ref 的 convert_prob 应与 None/ref 不同（价格负效应）"
    # 方向验证：高价 → 均值 convert_prob 降低（高价格 → 负特征 → 负 logit → 低概率）
    assert np.mean(oc_2x.convert_prob) < np.mean(
        oc_none.convert_prob
    ), "price_cny=2×ref 应导致 convert_prob 均值下降（价格弹性）"


# ═══════════════════════════════════════ AT-M4-04 ═══════════════════════════


def test_at_m4_04_price_monotonicity():
    """sandbox price +30% → conversions/revenue 单调下降；-30% → 单调上升.

    方向与幅度合理：下降幅度 > 0 且 < 100%。
    """
    store = _make_sandbox()
    sc = _make_scenario()
    sess = store.create(sc)
    base_conv = sess.current_result.total_kpis["conversions"]
    _base_rev = sess.current_result.total_kpis["revenue"]

    # price +30%（基准 45 → 58.5）
    sess_up = store.update(sess.id, {"price_cny": 45.0 * 1.3})
    conv_up = sess_up.current_result.total_kpis["conversions"]
    rev_up = sess_up.current_result.total_kpis["revenue"]

    # price -30%（基准 45 → 31.5）—— 需要新建 session 以回到原基线
    sess2 = store.create(sc)
    sess_dn = store.update(sess2.id, {"price_cny": 45.0 * 0.7})
    conv_dn = sess_dn.current_result.total_kpis["conversions"]
    rev_dn = sess_dn.current_result.total_kpis["revenue"]

    assert conv_up < base_conv, "price +30% 后 conversions 应下降"
    assert conv_dn > base_conv, "price -30% 后 conversions 应上升"
    assert 0 < base_conv - conv_up < base_conv, "下降幅度 > 0 且 < 100%"
    assert conv_dn - base_conv > 0, "上升幅度 > 0"

    assert rev_up > 0, "revenue 应为正"
    assert rev_dn > 0, "revenue 应为正"


# ═══════════════════════════════════════ AT-M4-05 ═══════════════════════════


def test_at_m4_05_price_budget_commutativity():
    """先价格后预算 vs 先预算后价格 最终 revenue 相等（rel_tol=1e-6）."""
    store = _make_sandbox()
    sc = _make_scenario()

    new_price = 45.0 * 1.3  # +30%
    new_budget = 5_000.0 * 2  # 2x

    # 路径 A: price first → budget
    sess_a = store.create(sc)
    store.update(sess_a.id, {"price_cny": new_price})
    store.update(sess_a.id, {"total_budget": new_budget})
    rev_a = sess_a.current_result.total_kpis["revenue"]

    # 路径 B: budget first → price
    sess_b = store.create(sc)
    store.update(sess_b.id, {"total_budget": new_budget})
    store.update(sess_b.id, {"price_cny": new_price})
    rev_b = sess_b.current_result.total_kpis["revenue"]

    assert math.isclose(
        rev_a, rev_b, rel_tol=1e-6
    ), f"价格×预算交换律失败: 路径A revenue={rev_a:.6f} ≠ 路径B revenue={rev_b:.6f}"


# ═══════════════════════════════════════ AT-M4-06 ═══════════════════════════


def test_at_m4_06_price_elif_uses_current_conversions():
    """price 补丁重算 revenue = 当前 session conversions × 新价，而非 baseline 隐含 45 元."""
    store = _make_sandbox()
    sc = _make_scenario()
    sess = store.create(sc)

    # Step 1: 先做 budget 补丁改变 conversions
    store.update(sess.id, {"total_budget": 5_000.0 * 2})
    _conv_after_budget = sess.current_result.total_kpis["conversions"]

    # Step 2: 再做 price 补丁
    new_price = 60.0
    store.update(sess.id, {"price_cny": new_price})
    conv_after_price = sess.current_result.total_kpis["conversions"]
    rev_after_price = sess.current_result.total_kpis["revenue"]

    # revenue 应 = price 补丁后的 conversions × 新价
    expected_revenue = conv_after_price * new_price
    assert math.isclose(
        rev_after_price, expected_revenue, rel_tol=1e-6
    ), f"price elif revenue={rev_after_price:.4f} ≠ conv({conv_after_price:.4f}) × price({new_price})"

    # 验证不是 baseline 隐含 45 元路径（baseline_conv × 45 ≠ 当前 revenue）
    baseline_conv = sess.baseline_result.total_kpis["conversions"]
    old_rev = baseline_conv * 45.0
    # 只要 budget 或 price 改变，new revenue 应与 old_rev 不同
    assert not math.isclose(
        rev_after_price, old_rev, rel_tol=1e-4
    ), "revenue 不应等于 baseline conversions × 45（应使用当前 conversions × 新价）"


# ═══════════════════════════════════════ AT-M4-07 ═══════════════════════════


def test_at_m4_07_reference_price_getter():
    """reference_prices() 可用；缺 reference_price 字段时有合理默认并标注「未标定」."""
    from oransim.config.niches import reference_prices

    prices, uncalibrated = reference_prices()

    # 返回类型正确
    assert isinstance(prices, dict), "reference_prices() 第一返回值应为 dict"
    assert isinstance(uncalibrated, set), "reference_prices() 第二返回值应为 set"

    # 至少有 beauty/food 等基础品类
    for niche in ("beauty", "food", "fitness"):
        assert niche in prices, f"reference_prices 缺少品类 '{niche}'"
        assert prices[niche] > 0, f"品类 '{niche}' 的 reference_price 应 > 0"

    # niches.json 目前没有 reference_price 字段 → 全部应在 uncalibrated 集合中
    assert len(uncalibrated) > 0, "当前 niches.json 未设 reference_price，应全部标为未标定"

    # 未标定 niche 的价格仍为合理正数
    for niche in uncalibrated:
        assert prices.get(niche, 0) > 0, f"未标定品类 '{niche}' 的默认价格应 > 0"


# ═══════════════════════════════════════ AT-M4-08 ═══════════════════════════


def test_at_m4_08_decision_weights_frozen():
    """W_CLICK/W_ENGAGE/W_CONVERT 数值与改造前一致（常量快照断言）.

    只允许新增价格项系数 W_PRICE_SENS（单独新增，不改原三组权重）。
    """
    from oransim.agents.statistical import StatisticalAgents

    # 改造前冻结值（来自 statistical.py 原始 PR）
    expected_w_click = np.array([1.8, 1.2, 0.9, 0.4, -0.7, 0.25, 0.3], dtype=np.float32)
    expected_w_engage = np.array([1.4, 0.9, 0.6, 0.5, -0.3, 0.4], dtype=np.float32)
    expected_w_convert = np.array([1.1, 0.6, 0.7, 0.8, 0.35], dtype=np.float32)

    np.testing.assert_array_equal(
        StatisticalAgents.W_CLICK,
        expected_w_click,
        err_msg="W_CLICK 被修改，违反权重冻结（铁律 4）",
    )
    np.testing.assert_array_equal(
        StatisticalAgents.W_ENGAGE,
        expected_w_engage,
        err_msg="W_ENGAGE 被修改，违反权重冻结（铁律 4）",
    )
    np.testing.assert_array_equal(
        StatisticalAgents.W_CONVERT,
        expected_w_convert,
        err_msg="W_CONVERT 被修改，违反权重冻结（铁律 4）",
    )

    # 新增价格系数必须存在且为负（高价 → 负效应）
    assert hasattr(
        StatisticalAgents, "W_PRICE_SENS"
    ), "StatisticalAgents 缺少 W_PRICE_SENS 属性（价格敏感度系数）"
    w_ps = float(StatisticalAgents.W_PRICE_SENS)
    assert w_ps < 0, f"W_PRICE_SENS 应为负数（高价→负效应），实际={w_ps}"


# ═══════════════════════════════════════ AT-M4-01b hash_tuple ════════════════


def test_at_m4_01b_new_scenario_fields_in_hash():
    """price_cny / pricing_model / substitute_pressure 三字段已进 hash_tuple().

    Iron Rule 4: 新 Scenario 字段必须通过 hash_tuple()。
    AT-M3-08 最终覆盖此三件套，但 M4 需 price_cny 先行入 hash。
    """
    from oransim.causal.counterfactual import Scenario

    base_cre = _make_creative("m4-hash")
    base = dict(
        creative=base_cre,
        total_budget=5_000.0,
        platform_alloc={"douyin": 1.0},
        seed=0,
    )
    s0 = Scenario(**base)
    s_price = Scenario(**{**base, "price_cny": 99.0})
    s_model = Scenario(**{**base, "pricing_model": "subscription"})
    s_press = Scenario(**{**base, "substitute_pressure": 0.5})

    assert s0.hash_tuple() != s_price.hash_tuple(), "price_cny 变化应改变 hash_tuple()"
    assert s0.hash_tuple() != s_model.hash_tuple(), "pricing_model 变化应改变 hash_tuple()"
    assert s0.hash_tuple() != s_press.hash_tuple(), "substitute_pressure 变化应改变 hash_tuple()"
