"""causal/launch_interventions.py — 命名上市干预弹药库 (方案 §4.6).

固化一组命名 do() 补丁, 全部骑现有 `ScenarioRunner.counterfactual()` (保留 abducted
U 的 Pearl 三步) 与图级 do(), 零新机制——不写任何 KPI 乘子 hack (规范 §7.3 红线)。

价格反事实 = 图级 do(price_point): 拷贝 baseline、改 price_cny、过
`ScenarioRunner.counterfactual()` (fixed_u 复用 baseline abducted U), 价格经
simulate(price_cny=)/aggregate_kpis(price_cny=) 自然流过, 不直接乘系数。

产品诚实规则 (逐字执行, 铁律 2): 竞品响应类输出永远以「分支」(labeled branch)
呈现, 渲染文案含固定前缀「如果竞品跟进——这是分支不是预测」。

依赖方向: causal 内部, 不 import spec (REG-4)。零改动 counterfactual/fixed_point/
cate/population/equilibrium_under_do (AT-M6-07)。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

# 竞品分支固定前缀 (产品诚实规则, AT-M6-06)
COMPETITOR_BRANCH_PREFIX = "如果竞品跟进——这是分支不是预测"

# 8 个 do() 字典 (方案 §4.6 表; price 上下行算 2 条)
INTERVENTION_NAMES = (
    "organic_only",
    "price_up_30",
    "price_down_30",
    "channel_concentration",
    "no_kol_launch",
    "bad_market",
    "compliance_block",
    "competitor_response",
)


@dataclass
class InterventionResult:
    name: str
    kpi: dict[str, float]
    delta: dict[str, float]
    branch: bool = False                 # 竞品响应类为 True
    label: str = ""
    note: str = ""
    paid_events: int | None = None       # organic_only 专用
    extra: dict[str, Any] = field(default_factory=dict)


def _kpi_delta(base: dict, new: dict) -> dict[str, float]:
    out = {}
    for k, bv in base.items():
        nv = new.get(k)
        if isinstance(bv, (int, float)) and isinstance(nv, (int, float)):
            out[k] = float(nv - bv)
    return out


def _scale_price(scenario, factor: float):
    cf = copy.copy(scenario)
    base_price = scenario.price_cny if scenario.price_cny is not None else 45.0
    cf.price_cny = base_price * factor
    return cf


def _run_cf(runner, modified_baseline, baseline_result, intervention: dict):
    """图级 do(): 走现有 counterfactual (fixed_u=baseline abducted U, Pearl 三步)。"""
    return runner.counterfactual(modified_baseline, baseline_result, intervention)


def run_intervention(
    name: str,
    scenario,
    runner,
    baseline_result,
) -> InterventionResult:
    """对单条命名干预产出 KPI delta。scenario=baseline Scenario,
    baseline_result=runner.run(scenario) 的结果 (提供 abducted U)。"""
    base_kpi = baseline_result.total_kpis

    if name == "price_up_30":
        cf = _scale_price(scenario, 1.3)
        res = _run_cf(runner, cf, baseline_result, {})
        return InterventionResult(name, res.total_kpis, _kpi_delta(base_kpi, res.total_kpis),
                                  label="价格 +30%", note="价格弹性 (图级 do(price_point))")

    if name == "price_down_30":
        cf = _scale_price(scenario, 0.7)
        res = _run_cf(runner, cf, baseline_result, {})
        return InterventionResult(name, res.total_kpis, _kpi_delta(base_kpi, res.total_kpis),
                                  label="价格 -30%", note="价格弹性 (图级 do(price_point))")

    if name == "no_kol_launch":
        res = _run_cf(runner, scenario, baseline_result, {"kol_per_platform": None})
        return InterventionResult(name, res.total_kpis, _kpi_delta(base_kpi, res.total_kpis),
                                  label="不请达人", note="kol_per_platform=None")

    if name == "channel_concentration":
        # 全压第一个平台
        first = next(iter(scenario.platform_alloc))
        res = _run_cf(runner, scenario, baseline_result, {"platform_alloc": {first: 1.0}})
        return InterventionResult(name, res.total_kpis, _kpi_delta(base_kpi, res.total_kpis),
                                  label=f"渠道集中 ({first})", note="单平台 alloc=1.0")

    if name == "bad_market":
        cf = copy.copy(scenario)
        cf.macro_cvr_lift = scenario.macro_cvr_lift * 0.6
        cf.macro_ctr_lift = scenario.macro_ctr_lift * 0.7
        res = _run_cf(runner, cf, baseline_result, {})
        return InterventionResult(name, res.total_kpis, _kpi_delta(base_kpi, res.total_kpis),
                                  label="市场逆风", note="macro sentiment 负面")

    if name == "compliance_block":
        # creative audit_risk 触发: 改 creative → 全重跑 (新 abduction)
        from oransim.data.creatives import make_creative
        cf = copy.copy(scenario)
        cf.creative = make_creative(
            creative_id="ci_compliance_block",
            caption=f"{scenario.creative.caption} 最 第一 100% 无效退款",  # 触发 audit_risk
            duration_sec=scenario.creative.duration_sec,
        )
        res = runner.run(cf, n_monte_carlo=5)
        return InterventionResult(name, res.total_kpis, _kpi_delta(base_kpi, res.total_kpis),
                                  label="合规被卡", note="audit_risk 高 → 限流")

    if name == "organic_only":
        # treatment_boost_factor=0: 剥离 paid_ 种子 → 无付费事件 (白送的扩散能力)。
        # KPI delta = 扩散预测 (全量 vs 纯自然) 的事件总量差 (重跑预测, 非乘子 hack)。
        from oransim.diffusion.hawkes import ParametricHawkes
        full_seed = [(0.0, "paid_impression"), (0.0, "impression"), (30.0, "like"),
                     (60.0, "paid_impression"), (90.0, "share")]
        organic_seed = [(t, n) for (t, n) in full_seed if not str(n).startswith("paid_")]
        paid_events = sum(1 for (_t, n) in organic_seed if str(n).startswith("paid_"))
        model = ParametricHawkes()
        fc_full = model.forecast(full_seed)
        fc_org = model.forecast(organic_seed)
        delta = _kpi_delta(fc_full.per_type_totals, fc_org.per_type_totals)
        return InterventionResult(
            name, dict(fc_org.per_type_totals), delta, paid_events=paid_events,
            label="纯自然量", note="treatment_boost_factor=0；paid 事件为 0",
            extra={"organic_seed_len": len(organic_seed),
                   "full_total": fc_full.per_type_totals},
        )

    if name == "competitor_response":
        # 竞品响应: competitor_action 节点干预 + equilibrium_under_do; 标注为分支。
        # KPI delta = do(competitor) 均衡 vs baseline 均衡 的 SCC 节点值差 (图级, 非乘子)。
        from .scm import equilibrium_under_do
        sp = scenario.substitute_pressure if scenario.substitute_pressure is not None else 0.5
        eq_base = equilibrium_under_do({})
        eq_do = equilibrium_under_do({"competitor_action": float(sp)})
        delta = _kpi_delta(eq_base["equilibrium"], eq_do["equilibrium"])
        return InterventionResult(
            name, dict(eq_do["equilibrium"]), delta, branch=True,
            label=f"{COMPETITOR_BRANCH_PREFIX}：竞品 substitute_pressure={sp}",
            note="competitor_action do() + equilibrium_under_do",
            extra={"equilibrium_converged": eq_do["converged"],
                   "spectral_radius": eq_do["spectral_radius"]},
        )

    raise ValueError(f"unknown intervention: {name!r}. Available: {INTERVENTION_NAMES}")


def substitute_pressure_to_exogenous(substitute_pressure: float | None) -> dict[str, float]:
    """把 substitute_pressure 接到既有 competitor_action 节点 (AT-M6-05)。

    None → 空 dict (competitor_action 行为与现状一致, 不注入外生值)。
    """
    if substitute_pressure is None:
        return {}
    return {"competitor_action": float(substitute_pressure)}
