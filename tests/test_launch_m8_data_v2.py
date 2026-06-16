"""AT-M8-xx 数据 v2 + 标定 acceptance tests.

AT-M8-01 niches.json v2 向后兼容 — 老字段/既有 getter 不变；REG-2 快照绿（另测覆盖）
AT-M8-02 新 getter 与新品类完整性 — reference_prices/adoption_priors/bass_priors 全覆盖
AT-M8-03 标定可追溯 — 标定前后分位带变化有记录；未标定项标注；来源标「合成自标定」
AT-M8-04 黄金集准确率不回退 — 扩品类后 AT-M2-01 仍 ≥85%；B2B 仍硬拒绝
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

GOLDEN = Path(__file__).parent / "golden" / "launch_ideas.jsonl"

# 原 10 campaign 品类 (v1 基线)
_V1_KEYS = [
    "beauty",
    "fashion",
    "food",
    "beverage",
    "fitness",
    "electronics",
    "travel",
    "home",
    "pet",
    "parenting",
]


# ═══════════════════════════════════════ AT-M8-01 ═══════════════════════════


def test_at_m8_01_v2_backward_compatible():
    """v2 对老字段只增不改不删；既有 campaign getter 输出与 v1 一致."""
    from oransim.config import niches as n

    # campaign 域 getter 默认仍是原 10 (kol 库 + predict 依赖, REG-2)
    assert n.niche_keys() == _V1_KEYS, "niche_keys() 默认应保持 campaign 原 10"

    # 既有 getter 对原 10 的值逐键不变 (老字段未被改)
    ctr = n.ctr_priors()
    assert set(ctr.keys()) == set(_V1_KEYS), "ctr_priors() 默认不应含 v2 品类"
    assert ctr["beauty"] == {"mu": 0.048, "sigma": 0.02, "n": 3100}, "beauty ctr 老值被改"

    syn = n.synonyms()
    assert set(syn.keys()) == set(_V1_KEYS)
    assert "美妆" in syn["beauty"], "beauty synonyms 老值缺失"

    # en_to_zh / bias_captions 默认仍原 10
    assert set(n.en_to_zh().keys()) == set(_V1_KEYS)
    assert set(n.bias_captions().keys()) == set(_V1_KEYS)

    # 原 niche 在 raw json 里老字段仍在 (只增不改不删)
    raw = json.loads((BACKEND.parent / "data" / "niches.json").read_text(encoding="utf-8"))
    beauty = next(x for x in raw["niches"] if x["key"] == "beauty")
    for old_field in ("key", "zh", "en", "synonyms", "ctr_prior", "bias_caption", "female_ratio"):
        assert old_field in beauty, f"老字段 {old_field} 被删"


# ═══════════════════════════════════════ AT-M8-02 ═══════════════════════════


def test_at_m8_02_new_getters_complete():
    """reference_prices/adoption_priors/bass_priors 对全部品类（含新 5）返回完整值."""
    from oransim.config import niches as n

    all_keys = set(n.niche_keys(include_v2=True))
    assert len(all_keys) == 15, "应有 15 品类 (原 10 + 新 5)"
    new5 = all_keys - set(_V1_KEYS)
    assert len(new5) == 5

    rp, rp_unc = n.reference_prices()
    ap, ap_unc = n.adoption_priors()
    bp, bp_unc = n.bass_priors()

    for getter_name, (vals, unc) in {
        "reference_prices": (rp, rp_unc),
        "adoption_priors": (ap, ap_unc),
        "bass_priors": (bp, bp_unc),
    }.items():
        # 全部品类有值
        assert all_keys <= set(vals), f"{getter_name} 未覆盖全部品类"
        for k in all_keys:
            assert vals[k] is not None
        # 缺字段的（原 10 无 v2 字段）走默认 + 未标定标注
        assert set(_V1_KEYS) <= unc, f"{getter_name} 原 10 应标未标定 (无 json 字段走默认)"
        # 新 5 有 json 字段 → 已标定 (不在 uncalibrated)
        assert not (new5 & unc), f"{getter_name} 新品类有 json 字段不应未标定"

    # 新品类各有非空 synonyms
    syn_v2 = n.synonyms(include_v2=True)
    for k in new5:
        assert syn_v2.get(k), f"新品类 {k} 应有非空 synonyms"

    # bass_priors 结构含 p/q
    for k in all_keys:
        assert "p" in bp[k] and "q" in bp[k]


# ═══════════════════════════════════════ AT-M8-03 ═══════════════════════════


def test_at_m8_03_calibration_traceable(tmp_path):
    """标定前后同一输入分位带变化有记录；未标定项标注；来源标「合成自标定」."""
    from oransim.config import niches as n
    from oransim.spec.calibration import calibration_trace

    rec = tmp_path / "cal_trace.json"
    # 同一固定输入 (niche=beauty 未标定 → 用 fallback) 的标定 trace
    trace = calibration_trace("beauty", record_path=rec)
    assert "before" in trace and "after" in trace, "应记录标定前后"
    assert trace["before"] != trace["after"] or trace["uncalibrated"] is True
    # 未标定项显式标注
    _, unc = n.reference_prices()
    assert "beauty" in unc, "beauty 当前未标定"
    assert trace["uncalibrated"] is True
    # 来源标注「合成数据自标定，非真实校准」
    assert "合成数据自标定" in trace["source"] and "非真实校准" in trace["source"]

    # 落盘记录可读 (before/after 对照基线文件)
    rec_path = trace["record_path"]
    assert Path(rec_path).exists(), "标定记录应落盘"
    rec = json.loads(Path(rec_path).read_text(encoding="utf-8"))
    assert "beauty" in rec

    # 已标定品类 (app_tool, niches.json v2 有字段) → before≠after 变化有记录
    cal = calibration_trace("app_tool", record_path=rec_path)
    assert cal["uncalibrated"] is False, "app_tool 有 v2 字段应已标定"
    assert cal["before"] != cal["after"], "已标定品类应有可追溯的分位带变化"


# ═══════════════════════════════════════ AT-M8-04 ═══════════════════════════


def test_at_m8_04_golden_accuracy_no_regression():
    """扩品类与 synonyms 后重跑 AT-M2-01 → 准确率仍 ≥85%；3 条 B2B 反例仍硬拒绝."""
    import os

    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.extract import extract_spec
    from oransim.spec.ground import ground

    rows = [
        json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    positives = [r for r in rows if not r.get("expect_reject")]
    b2b = [r for r in rows if r.get("reject_reason") == "b2b"]

    ok = sum(
        1
        for r in positives
        if not (g := ground(extract_spec(r["idea_text"]))).rejected
        and g.niche_key == r["expected_niche_key"]
    )
    rate = ok / len(positives)
    print(f"\n[AT-M8-04] golden accuracy after v2: {ok}/{len(positives)} = {rate:.1%}")
    assert rate >= 0.85, f"扩品类后准确率 {rate:.1%} 回退到 85% 以下"

    assert len(b2b) >= 3
    for r in b2b:
        assert ground(extract_spec(r["idea_text"])).rejected, f"B2B 漏过: {r['idea_text'][:24]}"


# ═══════════════════════════════════════ M8 live 复跑 ════════════════════════


@pytest.mark.live_llm
def test_at_m8_live_golden_accuracy_after_v2():
    """M8 live 复跑: 扩 v2 品类后用真实 LLM 抽取重跑黄金集准确率 ≥85%、B2B 仍拒绝。

    skip-by-default (@live_llm)。运行: 设 LLM_MODE=api + LLM_API_KEY 后
    `pytest -k m8_live --run-live`。与 mock 的 AT-M8-04 分别记录 (用例集 §8.3)。
    """
    os.environ["LLM_MODE"] = "api"
    from oransim.agents.soul_llm import llm_available

    if not llm_available():
        pytest.skip("no live LLM provider available")

    from oransim.spec.extract import extract_spec
    from oransim.spec.ground import ground

    rows = [
        json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    positives = [r for r in rows if not r.get("expect_reject")]
    b2b = [r for r in rows if r.get("reject_reason") == "b2b"]

    ok = sum(
        1
        for r in positives
        if not (g := ground(extract_spec(r["idea_text"]))).rejected
        and g.niche_key == r["expected_niche_key"]
    )
    rate = ok / len(positives)
    print(f"\n[M8 LIVE] golden accuracy after v2: {ok}/{len(positives)} = {rate:.1%}")
    assert rate >= 0.85, f"live 扩品类后准确率 {rate:.1%} < 85%"
    for r in b2b:
        assert ground(
            extract_spec(r["idea_text"])
        ).rejected, f"live: B2B 漏过 {r['idea_text'][:24]}"
