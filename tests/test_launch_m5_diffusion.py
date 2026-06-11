"""AT-M5-xx 人格 + 传播 acceptance tests.

AT-M5-01 事件别名双处同步 — trial/adoption/wom_referral 在 hawkes 与 neural_hawkes 一致
AT-M5-02 90 天 horizon — DiffusionConfig(horizon_days=90) → daily_buckets 长度 90；默认 14
AT-M5-03 Bass 饱和形状 — 峰值 + 趋平 + 闭式对照 + 饱和边界（核心保真度）
AT-M5-04 拼接窗无硬接缝 — day 14 附近无强度跳变
AT-M5-05 registry 注册 — get_diffusion_model("bass_saturated_hawkes") 实现 ABC
AT-M5-06 市场潜量 m — fan_weight 加权质量 × adoption_rate_prior；不同 niche 不同；POP 不被写
AT-M5-07 launch 人格模式 — infer_batch(mode="launch") 四键齐全；默认 mode 行为不变
AT-M5-08 voronoi 校准换票源 — launch 用 will_try 票；campaign 用点击票
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ═══════════════════════════════════════ AT-M5-01 ═══════════════════════════

_ALIAS_EXPECTED = {
    "trial": "conversion",
    "adoption": "conversion",
    "wom_referral": "share",
}
_BASE_TYPES = ("impression", "like", "comment", "share", "save", "conversion")


@pytest.mark.parametrize("alias,base", list(_ALIAS_EXPECTED.items()))
def test_at_m5_01_event_alias_sync(alias, base):
    """trial/adoption/wom_referral 在两个映射函数里索引一致, 且 = 对应基类型索引."""
    from oransim.diffusion.hawkes import ParametricHawkes
    from oransim.diffusion.neural_hawkes import CausalNeuralHawkesProcess

    ph = ParametricHawkes()
    nh = CausalNeuralHawkesProcess()

    base_idx = ph.config.event_types.index(base)
    assert ph._event_type_idx(alias) == base_idx, f"hawkes: {alias} 应映射到 {base}"
    assert nh._etype_idx(alias) == base_idx, f"neural: {alias} 应映射到 {base}"
    # 两处一致
    assert ph._event_type_idx(alias) == nh._etype_idx(alias)


@pytest.mark.parametrize("base", _BASE_TYPES)
def test_at_m5_01b_base_and_paid_not_regressed(base):
    """六种基类型 + paid_ 前缀既有行为不回归 (双处)."""
    from oransim.diffusion.hawkes import ParametricHawkes
    from oransim.diffusion.neural_hawkes import CausalNeuralHawkesProcess

    ph = ParametricHawkes()
    nh = CausalNeuralHawkesProcess()
    bi = ph.config.event_types.index(base)
    assert ph._event_type_idx(base) == bi
    assert nh._etype_idx(base) == bi
    # paid_ 前缀归一到基类型
    assert ph._event_type_idx(f"paid_{base}") == bi
    assert nh._etype_idx(f"paid_{base}") == bi


# ═══════════════════════════════════════ AT-M5-02 ═══════════════════════════


def test_at_m5_02_90day_horizon():
    """DiffusionConfig(horizon_days=90) → daily_buckets 长度 90；默认 config 仍 14."""
    from oransim.diffusion.base import DiffusionConfig
    from oransim.diffusion.hawkes import ParametricHawkes, ParametricHawkesConfig

    # 默认仍 14
    default_model = ParametricHawkes()
    assert default_model.config.horizon_days == 14

    # 90 天 config
    cfg90 = ParametricHawkesConfig(horizon_days=90)
    model90 = ParametricHawkes(cfg90)
    seed_events = [(0.0, "impression"), (5.0, "impression"), (10.0, "like")]
    fc = model90.forecast(seed_events)
    assert len(fc.daily_buckets) == 90, f"daily_buckets 应为 90 天，实际 {len(fc.daily_buckets)}"

    # 默认 14 天 forecast 仍 14 桶 (campaign 不变)
    fc14 = default_model.forecast(seed_events)
    assert len(fc14.daily_buckets) == 14
