"""AT-M6-xx SCM + 干预弹药库 acceptance tests.

AT-M6-01 图结构只增不改 — 新增恰 price_point + launch_channel_mix 两节点+边；旧图全在
AT-M6-02 新图收敛 — equilibrium_under_do 收敛、谱半径 < 1
AT-M6-03 七/八条命名干预各出非空 KPI delta + 方向性
AT-M6-04 价格反事实是图级 do() — 共享 abducted U，无 KPI 乘子 hack
AT-M6-05 substitute_pressure 接线 — 喂既有 competitor_action；None 行为不变
AT-M6-06 competitor_response 分支标注 — branch=True + 固定前缀文案
AT-M6-07 零改动模块未触碰 — 受保护面未被 M6 改动 (依赖方向)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _runner_and_baseline(platform_alloc=None, with_kol=True):
    from oransim.agents.statistical import StatisticalAgents
    from oransim.causal.counterfactual import Scenario, ScenarioRunner
    from oransim.data.creatives import make_creative
    from oransim.data.kols import generate_kol_library, pick_kol_by_spec
    from oransim.data.population import generate_population
    from oransim.platforms.xhs.world_model_legacy import PlatformWorldModel

    pop = generate_population(N=800, seed=42)
    runner = ScenarioRunner(PlatformWorldModel(pop), StatisticalAgents(pop))
    alloc = platform_alloc or {"douyin": 0.6, "xhs": 0.4}
    kpp = None
    if with_kol:
        kols = generate_kol_library(n_per_platform=10)
        kpp = {p: pick_kol_by_spec(kols, p, niche="beauty") for p in alloc}
    cre = make_creative(creative_id="m6-base", caption="新品面膜 上市种草", duration_sec=15.0)
    sc = Scenario(
        creative=cre,
        total_budget=50000.0,
        platform_alloc=alloc,
        kol_per_platform=kpp,
        seed=42,
        price_cny=89.0,
        substitute_pressure=0.5,
    )
    base = runner.run(sc, n_monte_carlo=5)
    return runner, sc, base


# ═══════════════════════════════════════ AT-M6-01 ═══════════════════════════


def test_at_m6_01_graph_additive_only():
    """新图 = 旧图 + price_point + launch_channel_mix 两节点；旧节点/边全在."""
    from oransim.causal import scm

    names = {n.name for n in scm.NODES}
    assert "price_point" in names and "launch_channel_mix" in names

    # 旧图代表性节点/边仍在 (只增不改)
    old_repr_nodes = {
        "competitor_action",
        "total_budget",
        "platform_alloc",
        "conversion",
        "click",
        "impression_dist",
        "audience_match",
        "direct_revenue",
        "add_to_cart",
    }
    assert old_repr_nodes <= names, "旧图节点缺失 — 违反只增不改"

    edges = {(s, t) for s, t in scm.EDGES}
    old_repr_edges = {
        ("competitor_action", "ecpm_bid"),
        ("total_budget", "impression_dist"),
        ("platform_alloc", "impression_dist"),
        ("conversion", "direct_revenue"),
        ("add_to_cart", "conversion"),
    }
    assert old_repr_edges <= edges, "旧图边缺失 — 违反只增不改"

    # 新增节点恰为这两个 (L3 可干预)
    new_nodes = [n for n in scm.NODES if n.name in ("price_point", "launch_channel_mix")]
    for n in new_nodes:
        assert n.layer == "L3" and n.intervenable, f"{n.name} 应为 L3 可干预节点"

    # 新增边含价格弹性 + 渠道分发
    assert ("price_point", "conversion") in edges
    assert ("launch_channel_mix", "impression_dist") in edges


# ═══════════════════════════════════════ AT-M6-02 ═══════════════════════════


def test_at_m6_02_new_graph_converges():
    """新图上 equilibrium_under_do 收敛、谱半径 < 1 (baseline + 命名 do())."""
    from oransim.causal.scm import equilibrium_under_do

    base = equilibrium_under_do()
    assert base["converged"] is True
    assert base["spectral_radius"] < 1.0

    for do in [
        {"price_point": 1.3},
        {"launch_channel_mix": 1.0},
        {"competitor_action": 0.8},
        {"total_budget": 2.0},
    ]:
        eq = equilibrium_under_do(do)
        assert eq["converged"] is True, f"do {do} 未收敛"
        assert eq["spectral_radius"] < 1.0, f"do {do} 谱半径 ≥ 1"


# ═══════════════════════════════════════ AT-M6-03 ═══════════════════════════


def test_at_m6_03_named_interventions_deltas():
    """全部命名干预逐条跑通、各出非空 KPI delta + 方向性断言."""
    from oransim.causal.launch_interventions import INTERVENTION_NAMES, run_intervention

    runner, sc, base = _runner_and_baseline()
    results = {nm: run_intervention(nm, sc, runner, base) for nm in INTERVENTION_NAMES}

    # 全部 8 条产出非空 delta
    for nm, r in results.items():
        assert r.delta, f"{nm} 应产出非空 KPI delta"

    # 方向性 (固定 seed)
    assert results["price_up_30"].delta["conversions"] < 0, "price_up_30 → adopters 下降"
    assert results["price_down_30"].delta["conversions"] > 0, "price_down_30 → adopters 上升"
    assert results["no_kol_launch"].delta["clicks"] < 0, "no_kol_launch → reach(点击) 下降"
    assert results["organic_only"].paid_events == 0, "organic_only → paid 事件为 0"


# ═══════════════════════════════════════ AT-M6-04 ═══════════════════════════


def test_at_m6_04_price_is_graph_level_do():
    """价格反事实走 counterfactual Pearl 三步: 共享 baseline abducted U，无 KPI 乘子."""
    from oransim.causal.launch_interventions import run_intervention

    runner, sc, base = _runner_and_baseline()

    # spy runner.run 捕获 fixed_u
    seen = {}
    orig_run = runner.run

    def _spy_run(scenario, fixed_u=None, fixed_idx=None, n_monte_carlo=1):
        if fixed_u is not None:
            seen["fixed_u"] = fixed_u
        return orig_run(scenario, fixed_u=fixed_u, fixed_idx=fixed_idx, n_monte_carlo=n_monte_carlo)

    runner.run = _spy_run
    try:
        r = run_intervention("price_up_30", sc, runner, base)
    finally:
        runner.run = orig_run

    # counterfactual 复用了 baseline 的 abducted_u (Pearl abduction 保留)
    assert "fixed_u" in seen, "价格反事实未走 fixed_u 路径 (非 Pearl 三步)"
    for plat, u in base.abducted_u.items():
        assert plat in seen["fixed_u"], f"平台 {plat} 的 abducted U 未被复用"
        np.testing.assert_array_equal(seen["fixed_u"][plat], u)

    # 价格确实改变了 KPI (经 simulate/aggregate 自然流过, 非乘子)
    assert r.delta.get("conversions", 0) != 0


# ═══════════════════════════════════════ AT-M6-05 ═══════════════════════════


def test_at_m6_05_substitute_pressure_wiring():
    """substitute_pressure 喂既有 competitor_action 节点；None → 行为不变."""
    from oransim.causal.launch_interventions import substitute_pressure_to_exogenous
    from oransim.causal.scm import equilibrium_under_do

    # None → 空 exogenous (competitor_action 行为与现状一致)
    assert substitute_pressure_to_exogenous(None) == {}
    # 有值 → 接到 competitor_action 节点
    exo = substitute_pressure_to_exogenous(0.7)
    assert exo == {"competitor_action": 0.7}

    # None 时均衡 = 不传 exogenous 的均衡 (行为不变)
    eq_none = equilibrium_under_do({}, exogenous=substitute_pressure_to_exogenous(None))
    eq_default = equilibrium_under_do({})
    assert eq_none["equilibrium"] == eq_default["equilibrium"]

    # competitor_action 节点确实存在 (既有, 非新增)
    from oransim.causal import scm

    assert any(n.name == "competitor_action" for n in scm.NODES)


# ═══════════════════════════════════════ AT-M6-06 ═══════════════════════════


def test_at_m6_06_competitor_response_is_branch():
    """competitor_response 输出带分支标记 + 固定前缀文案 (诚实原则)."""
    from oransim.causal.launch_interventions import (
        COMPETITOR_BRANCH_PREFIX,
        run_intervention,
    )

    runner, sc, base = _runner_and_baseline()
    r = run_intervention("competitor_response", sc, runner, base)

    assert r.branch is True, "competitor_response 必须标 branch=True"
    assert COMPETITOR_BRANCH_PREFIX in r.label, "渲染文案必须含固定分支前缀"
    assert "分支不是预测" in r.label

    # 其它干预不是分支
    r2 = run_intervention("price_up_30", sc, runner, base)
    assert r2.branch is False


# ═══════════════════════════════════════ AT-M6-07 ═══════════════════════════


def test_at_m6_07_protected_modules_untouched():
    """零改动模块未被 M6 触碰 (依赖方向 + 受保护面完好).

    权威 guard 是提交纪律 (git diff 这些路径为空); 此测试做结构守护:
    受保护模块不反向 import launch_interventions, 关键面签名/行为完好。
    """
    import inspect

    from oransim.causal.cate import __name__ as _cate_name  # noqa: F401

    # 1. 受保护面存在且签名完好
    from oransim.causal.counterfactual import ScenarioRunner
    from oransim.causal.fixed_point import banach_iterate, solve_linear_scm  # noqa: F401
    from oransim.causal.scm import equilibrium_under_do
    from oransim.data.population import generate_population  # noqa: F401

    sig = inspect.signature(ScenarioRunner.counterfactual)
    assert list(sig.parameters) == ["self", "baseline", "baseline_result", "intervention"]

    # 2. 受保护模块不反向依赖 launch_interventions (单向: 新代码依赖它们)
    for mod_path in [
        "backend/oransim/data/population.py",
        "backend/oransim/causal/counterfactual.py",
        "backend/oransim/causal/fixed_point.py",
        "backend/oransim/causal/cate.py",
    ]:
        text = (Path(__file__).parent.parent / mod_path).read_text(encoding="utf-8")
        assert "launch_interventions" not in text, f"{mod_path} 不应 import launch_interventions"

    # 3. equilibrium_under_do 仍在 scm.py 且行为完好 (新节点未破坏求解)
    eq = equilibrium_under_do()
    assert eq["converged"] and eq["spectral_radius"] < 1.0
