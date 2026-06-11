"""diffusion/bass_saturated_hawkes.py — Bass 饱和 Hawkes (方案 §4.4 核心保真度).

薄包装器: 内部持有 parametric Hawkes 的创新/模仿先验, 对采纳强度乘以饱和因子
``(1 − N(t)/m)``。N(t) = 累计采纳数, m = 市场潜量。结果: 90 天采纳曲线不再永远
增长, 出现峰值与饱和拐点 (经典 Bass 扩散)。

Bass 均场动力学 (确定性, 与闭式 Bass 一致):
    dN/dt = (p + q · N/m) · (m − N)
p = 创新系数 (外部驱动, 对应 Hawkes 基率 μ), q = 模仿系数 (口碑自激, 对应 Hawkes
分支)。p/q 先验未标定前在报告显式标注 (niches.json v2 字段, M8 补)。

收入时间线 = 每日 conversion 桶 × price_cny (调用方算)。
依赖方向: diffusion → data/config (引擎内), 不 import spec (REG-4)。
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .base import DiffusionConfig, DiffusionForecast, DiffusionModel

# 未标定 Bass 先验 (报告需标注「未经真实数据标定」)
_DEFAULT_BASS_P = 0.03   # 创新系数
_DEFAULT_BASS_Q = 0.38   # 模仿系数 (q > p → 曲线有内部峰值)
_DEFAULT_M = 10_000.0     # 兜底市场潜量 (无 population 时)


def market_potential(population, niche: str) -> float:
    """市场潜量 m = fan_weight_vector(POP, niche) 加权质量 × adoption_rate_prior(niche).

    只读 population, 绝不写 (AT-M5-06 POP 守护栏)。不同 niche 经 adoption_rate_prior
    区分 → 不同 m。
    """
    from oransim.config import niches as _niches
    from oransim.data.fan_profile import fan_weight_vector

    w = fan_weight_vector(population, niche)        # (N,) 只读, mean-1 归一
    weighted_mass = float(w.sum())                  # 加权可达质量 (≈ N)
    rate = _niches.adoption_rate_prior(niche)
    return weighted_mass * rate


@dataclass
class BassSaturatedConfig(DiffusionConfig):
    """Bass 饱和配置: 在 DiffusionConfig 上加 p/q/m。"""
    bass_p: float = _DEFAULT_BASS_P
    bass_q: float = _DEFAULT_BASS_Q
    market_m: float = _DEFAULT_M
    sub_steps_per_day: int = 24   # Euler 子步 (日内积分精度)


class BassSaturatedHawkes(DiffusionModel):
    """Bass 饱和扩散 (DiffusionModel ABC 实现)。

    forecast() 用均场 Bass ODE 确定性积分出每日采纳 (conversion) 曲线, 天然出现
    峰值 + 趋平。saturation_factor(N) = (1 − N/m) 在 N→m 时趋零。
    """

    def __init__(self, config: BassSaturatedConfig | None = None):
        self.config = config or BassSaturatedConfig()

    # -------------------------------------------------------------- saturation
    def saturation_factor(self, n_cumulative: float) -> float:
        """饱和因子 (1 − N/m), 夹紧到 [0,1]。N→m → 0 (AT-M5-03 边界)。"""
        m = max(self.config.market_m, 1e-9)
        return max(0.0, 1.0 - n_cumulative / m)

    def _conversion_idx(self) -> int:
        et = self.config.event_types
        return et.index("conversion") if "conversion" in et else len(et) - 1

    # ----------------------------------------------------------------- forecast
    def forecast(
        self, seed_events: Iterable[tuple[float, str]], **kwargs: Any
    ) -> DiffusionForecast:
        """均场 Bass 积分: 每日新增采纳 = ΔN。daily_buckets 填 conversion 桶。"""
        p = float(self.config.bass_p)
        q = float(self.config.bass_q)
        m = float(self.config.market_m)
        days = int(self.config.horizon_days)
        steps = max(1, int(self.config.sub_steps_per_day))
        dt = 1.0 / steps

        # 种子注入: 初始已采纳数 (seed conversion/adoption 事件计数), 否则从 ~0 起步
        n = 0.0
        for _t, name in seed_events or []:
            base = name[5:] if name.startswith("paid_") else name
            if base in ("conversion", "adoption", "trial"):
                n += 1.0
        n = min(n, m * 0.01)  # 种子不超过 1% 潜量, 避免压制内生峰值

        conv_idx = self._conversion_idx()
        K = len(self.config.event_types)
        daily_buckets: list[list[float]] = [[0.0] * K for _ in range(days)]
        timeline: list[tuple[float, str, float]] = []
        total_conv = 0.0

        for day in range(days):
            day_new = 0.0
            for s in range(steps):
                sat = max(0.0, m - n)
                intensity = (p + q * n / m) * sat          # dN/dt
                dn = intensity * dt
                # 不越过 m
                dn = min(dn, max(0.0, m - n))
                n += dn
                day_new += dn
                t_min = (day + (s + 0.5) * dt) * 24 * 60
                timeline.append((t_min, "conversion", intensity))
            daily_buckets[day][conv_idx] = day_new
            total_conv += day_new

        per_type_totals = {name: 0.0 for name in self.config.event_types}
        per_type_totals["conversion"] = total_conv

        return DiffusionForecast(
            timeline=timeline,
            per_type_totals=per_type_totals,
            daily_buckets=daily_buckets,
            latent={
                "backend": "bass_saturated_hawkes",
                "p": p, "q": q, "m": m,
                "n_final": n,
                "calibrated": False,
                "note": "Bass p/q/m 未经真实数据标定 (niches.json v2 先验)",
            },
        )

    def counterfactual_forecast(
        self,
        seed_events: Iterable[tuple[float, str]],
        *,
        intervention: dict[str, Any],
        **kwargs: Any,
    ) -> DiffusionForecast:
        """do() 干预: 支持 market_m / bass_p / bass_q 覆盖后重跑。"""
        import copy

        cfg = copy.copy(self.config)
        for k in ("market_m", "bass_p", "bass_q"):
            if k in intervention:
                setattr(cfg, k, float(intervention[k]))
        return BassSaturatedHawkes(cfg).forecast(seed_events)

    def log_likelihood(self, events: Iterable[tuple[float, str]]) -> float:
        """均场近似 NLL 占位 (Bass 为确定性均场, 非点过程似然)。"""
        return 0.0

    def fit(self, dataset, *, val_dataset=None, **kwargs) -> dict[str, Any]:
        return {"status": "bass_saturated is analytic; no fit (p/q/m are priors)"}

    def save(self, path: str) -> None:  # pragma: no cover - analytic model
        pass

    @classmethod
    def load_pretrained(cls, path: str | None = None, **kwargs: Any) -> "BassSaturatedHawkes":
        # 解析模型, 无 checkpoint 概念
        return cls(**kwargs)


def bass_closed_form_cumulative(p: float, q: float, m: float, t: float) -> float:
    """闭式 Bass 累计采纳 N(t) = m · (1 − e^{−(p+q)t}) / (1 + (q/p) e^{−(p+q)t})."""
    if p <= 0:
        return 0.0
    e = math.exp(-(p + q) * t)
    return m * (1.0 - e) / (1.0 + (q / p) * e)


def blend_intensity_curves(
    curve_a: list[float],
    curve_b: list[float],
    *,
    splice_start: int = 10,
    splice_end: int = 18,
) -> list[float]:
    """day [splice_start, splice_end] 线性交叉淡化 curve_a→curve_b, 消除硬接缝.

    day < splice_start 用 a; day > splice_end 用 b; 窗内线性权重混合。两曲线等长。
    用于 90 天拼接: a = 神经 Hawkes (0–14 OOD 前), b = parametric 长尾 (AT-M5-04)。
    """
    n = min(len(curve_a), len(curve_b))
    out: list[float] = []
    span = max(1, splice_end - splice_start)
    for d in range(n):
        if d <= splice_start:
            out.append(curve_a[d])
        elif d >= splice_end:
            out.append(curve_b[d])
        else:
            wb = (d - splice_start) / span        # 0→1 across window
            out.append((1.0 - wb) * curve_a[d] + wb * curve_b[d])
    return out
