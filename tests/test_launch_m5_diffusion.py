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


# ═══════════════════════════════════════ AT-M5-05 ═══════════════════════════


def test_at_m5_05_registry_registration():
    """get_diffusion_model('bass_saturated_hawkes') 返回 DiffusionModel 实例；
    既有 parametric_hawkes / causal_neural_hawkes 注册不受影响."""
    from oransim.diffusion.base import DiffusionModel
    from oransim.diffusion.registry import get_diffusion_model, list_diffusion_models

    bass = get_diffusion_model("bass_saturated_hawkes")
    assert isinstance(bass, DiffusionModel), "bass 应实现 DiffusionModel ABC"
    assert hasattr(bass, "forecast") and hasattr(bass, "saturation_factor")

    # 既有注册仍可用
    assert isinstance(get_diffusion_model("parametric_hawkes"), DiffusionModel)
    cnh = get_diffusion_model("causal_neural_hawkes")
    assert isinstance(cnh, DiffusionModel)

    listed = list_diffusion_models()
    assert "bass_saturated_hawkes" in listed
    assert "parametric_hawkes" in listed and "causal_neural_hawkes" in listed


# ═══════════════════════════════════════ AT-M5-06 ═══════════════════════════


def test_at_m5_06_market_potential_m():
    """m = fan_weight 加权质量 × adoption_rate_prior；不同 niche 不同 m；POP 不被写入."""
    from oransim.data.population import generate_population
    from oransim.diffusion.bass_saturated_hawkes import market_potential

    pop = generate_population(N=2000, seed=42)

    # POP 守护栏: 取关键数组 checksum
    import hashlib
    def _checksum(arr):
        return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()
    before = (_checksum(pop.gender_idx), _checksum(pop.age_idx),
              _checksum(pop.city_idx), _checksum(pop.income))

    m_beauty = market_potential(pop, "beauty")
    m_food = market_potential(pop, "food")
    m_pet = market_potential(pop, "pet")

    after = (_checksum(pop.gender_idx), _checksum(pop.age_idx),
             _checksum(pop.city_idx), _checksum(pop.income))
    assert before == after, "market_potential 不应写入 POP 单例数组"

    # 公式成立 (正数) 且不同 niche 不同
    for mv in (m_beauty, m_food, m_pet):
        assert mv > 0
    assert m_beauty != m_food, "不同 niche 应产出不同 m"
    assert m_food != m_pet


# ═══════════════════════════════════════ AT-M5-03 ═══════════════════════════


def test_at_m5_03_bass_saturation_shape():
    """Bass 饱和形状: 单调 + N(90)≤m + 峰值趋平 + 闭式对照 + 饱和边界."""
    from oransim.diffusion.bass_saturated_hawkes import (
        BassSaturatedConfig,
        BassSaturatedHawkes,
        bass_closed_form_cumulative,
    )

    p, q, m = 0.03, 0.38, 10_000.0
    cfg = BassSaturatedConfig(horizon_days=90, bass_p=p, bass_q=q, market_m=m, seed=42)
    model = BassSaturatedHawkes(cfg)
    fc = model.forecast([(0.0, "impression")])

    conv_idx = model._conversion_idx()
    daily_new = [day[conv_idx] for day in fc.daily_buckets]
    assert len(daily_new) == 90

    # (1) 累计单调不减 且 N(90) ≤ m
    cum = np.cumsum(daily_new)
    assert np.all(np.diff(cum) >= -1e-9), "累计采纳应单调不减"
    assert cum[-1] <= m + 1e-6, f"N(90)={cum[-1]} 不应超过 m={m}"

    # (2) 日新增存在峰值 t_peak ∈ (0,90)，峰后 7 日均值 < 峰值 80% (趋平)
    t_peak = int(np.argmax(daily_new))
    assert 0 < t_peak < 89, f"峰值日 {t_peak} 应在 (0,90) 内部"
    post = daily_new[t_peak + 1: t_peak + 8]
    assert post, "峰后应有数据"
    assert np.mean(post) < 0.8 * daily_new[t_peak], "峰后 7 日均值应 < 峰值 80% (趋平)"

    # (3) 对照闭式 Bass: 逐日累计相对误差 ≤ 15%
    for d in range(5, 90, 10):
        closed = bass_closed_form_cumulative(p, q, m, float(d + 1))
        if closed > m * 0.01:
            rel = abs(cum[d] - closed) / closed
            assert rel <= 0.15, f"day {d}: 模拟累计 {cum[d]:.1f} vs 闭式 {closed:.1f} 相对误差 {rel:.2%} > 15%"

    # (4) 饱和因子边界: N→m → 强度趋零
    assert model.saturation_factor(m) == 0.0
    assert model.saturation_factor(0.999 * m) < 0.01
    assert abs(model.saturation_factor(0.0) - 1.0) < 1e-9


# ═══════════════════════════════════════ AT-M5-04 ═══════════════════════════


def test_at_m5_04_splice_window_no_hard_seam():
    """day 10–18 线性混合后，序列在 day 14 附近一阶差分无突变."""
    from oransim.diffusion.bass_saturated_hawkes import blend_intensity_curves

    # 两条同一过程的估计 (神经/parametric 在重叠区量级相近, 小偏移)。
    # 硬切会在 day 14 产生 |a-b| 的单点跳变; 线性混合把它摊到 8 天 → 无突变。
    curve_a = [100.0 - d for d in range(30)]        # slope -1
    curve_b = [97.0 - d for d in range(30)]         # slope -1, offset 3 (重叠区接近)
    blended = blend_intensity_curves(curve_a, curve_b, splice_start=10, splice_end=18)

    diffs = np.abs(np.diff(blended))
    seam_window = diffs[9:19]                         # day 14 附近
    outside = np.concatenate([diffs[2:9], diffs[19:29]])  # 窗外
    seam_max = seam_window.max()
    outside_max = outside.max()
    assert seam_max <= outside_max * 1.5 + 1e-9, (
        f"day14 附近一阶差分 {seam_max:.3f} > 窗外最大 {outside_max:.3f}×1.5 (硬接缝)"
    )

    # 对照: 硬切 (day≤14 用 a, day>14 用 b) 会在 day 14 产生远大于混合的跳变
    hard = [curve_a[d] if d <= 14 else curve_b[d] for d in range(30)]
    hard_seam = abs(hard[15] - hard[14])
    assert seam_max < hard_seam, "线性混合的接缝差分应远小于硬切"

    # 端点行为: 窗前 = a, 窗后 = b
    assert blended[5] == curve_a[5]
    assert blended[25] == curve_b[25]


# ═══════════════════════════════════════ AT-M5-07 ═══════════════════════════


def _soul_pool(n=12):
    from oransim.agents.soul import SoulAgentPool
    from oransim.data.population import generate_population
    pop = generate_population(N=600, seed=42)
    return SoulAgentPool(pop, n=n, seed=7)


def _creative():
    from oransim.data.creatives import make_creative
    return make_creative(creative_id="m5-cre", caption="新品上市 保湿面膜 种草", duration_sec=15.0)


def test_at_m5_07_launch_persona_mode():
    """infer_batch(mode='launch') mock 返回四键齐全且类型正确；默认 mode 行为不变."""
    pool = _soul_pool()
    cre = _creative()
    probs = {pid: 0.3 for pid in pool.personas}

    launch = pool.infer_batch(cre, probs, None, "xhs", n_sample=8, seed=7, mode="launch")
    assert launch, "launch 模式应返回结果"
    for r in launch:
        assert set(["will_try", "would_pay_cny", "objection", "purchase_intent_7d"]) <= set(r)
        assert isinstance(r["will_try"], bool)
        assert isinstance(r["would_pay_cny"], float) and r["would_pay_cny"] >= 0
        assert isinstance(r["objection"], str)
        assert isinstance(r["purchase_intent_7d"], float)
        assert 0.0 <= r["purchase_intent_7d"] <= 1.0

    # 默认 mode (不传) 行为不变: 仍是 campaign 的 will_click 语义键
    default = pool.infer_batch(cre, probs, None, "xhs", n_sample=8, seed=7)
    for r in default:
        assert "will_click" in r, "默认 mode 应保留 will_click 键 (campaign 回归)"
        assert "will_try" not in r, "默认 mode 不应出现 launch 专有键"


# ═══════════════════════════════════════ AT-M5-08 ═══════════════════════════


def test_at_m5_08_voronoi_calibration_vote_source():
    """campaign 用 will_click 票；launch 用 will_try 票 (calibrate_per_territory vote_field)."""
    from oransim.agents.calibration import VoronoiPartition, calibrate_per_territory

    # 构造 will_click 与 will_try 故意相反的 souls
    souls = []
    for i in range(6):
        souls.append({
            "persona_id": i,
            "source": "llm",
            "will_click": (i % 2 == 0),   # 偶数 click
            "will_try": (i % 2 == 1),     # 奇数 try (与 click 相反)
        })
    S = len(souls)
    partition = VoronoiPartition(
        soul_indices=np.arange(S),
        nearest=np.zeros(1, dtype=np.int32),
        weights=np.full(S, 1.0 / S, dtype=np.float32),
        feat_pop=np.zeros((1, 2), dtype=np.float32),
        feat_souls=np.zeros((S, 2), dtype=np.float32),
    )
    stats = {i: 0.2 for i in range(S)}

    cal_click = calibrate_per_territory(souls, partition, stats, vote_field="will_click")
    cal_try = calibrate_per_territory(souls, partition, stats, vote_field="will_try")

    assert cal_click["vote_field"] == "will_click"
    assert cal_try["vote_field"] == "will_try"
    # 票源不同 → 逐 soul verdict 相反
    assert cal_click["soul_verdicts"] != cal_try["soul_verdicts"], "换票源应改变 verdicts"
    for i in range(S):
        assert cal_click["soul_verdicts"][i] != cal_try["soul_verdicts"][i]


def test_at_m5_08b_voronoi_calibration_mode_plumbing(monkeypatch):
    """voronoi_calibration(mode='launch') 把 will_try 作为票源传给 calibrate (spy)."""
    import oransim.api_helpers as ah
    from oransim import api_state

    seen = {}

    def _spy(souls, partition, stats, persona_id_to_slot=None, vote_field="will_click", **kw):
        seen["vote_field"] = vote_field
        return {"global_factor": 1.0}

    monkeypatch.setattr(ah, "calibrate_per_territory", _spy)
    monkeypatch.setattr(ah, "calibration_summary", lambda cal: {})
    monkeypatch.setattr(api_state, "PARTITION", object(), raising=False)
    monkeypatch.setattr(api_state, "PERSONA_TO_SLOT", {}, raising=False)

    souls = [{"source": "llm", "persona_id": i, "will_click": True, "will_try": False}
             for i in range(6)]
    stats = {i: 0.2 for i in range(6)}

    ah.voronoi_calibration(souls, stats, mode="launch")
    assert seen["vote_field"] == "will_try"

    ah.voronoi_calibration(souls, stats, mode="campaign")
    assert seen["vote_field"] == "will_click"
