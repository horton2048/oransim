"""AT-M2-xx Grounding acceptance tests.

AT-M2-01 品类映射准确率 (mock) ≥85% — 黄金集正例 niche key 映射
AT-M2-03 B2B 反例硬拒绝 — 全部 B2B 例无 Scenario/spec_id、clarification 非空
AT-M2-04 置信度闸门语义 — <0.55 硬拒绝、>=0.55 通过 (边界含入)
AT-M2-05 UEB 双源注册 — product_categories + category_notes 可检索
AT-M2-06 语料覆盖拉低置信度 — 无覆盖 niche 置信度下降并触发拒绝
AT-M2-07 synonyms 优先于嵌入兜底 — 关键词命中时嵌入路径调用计数为 0
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

GOLDEN = Path(__file__).parent / "golden" / "launch_ideas.jsonl"


def _load_ideas() -> list[dict]:
    if not GOLDEN.exists():
        return []
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ground_idea(idea_text: str, bus=None):
    os.environ["LLM_MODE"] = "mock"
    from oransim.spec.extract import extract_spec
    from oransim.spec.ground import ground

    spec = extract_spec(idea_text)
    return ground(spec, bus=bus)


# ═══════════════════════════════════════ AT-M2-01 ═══════════════════════════


def test_at_m2_01_category_mapping_accuracy_mock():
    """黄金集正例 niche key 映射准确率 ≥ 85% (mock 模式)."""
    ideas = _load_ideas()
    assert ideas, f"Golden set missing at {GOLDEN}"

    positives = [e for e in ideas if not e.get("expect_reject")]
    assert positives, "need positive examples"

    ok = 0
    misses = []
    for e in positives:
        g = _ground_idea(e["idea_text"])
        expected = e["expected_niche_key"]
        if (not g.rejected) and g.niche_key == expected:
            ok += 1
        else:
            misses.append((expected, g.niche_key, g.rejected, e["idea_text"][:24]))

    total = len(positives)
    rate = ok / total
    threshold = 0.85
    print(f"\n[AT-M2-01] niche mapping accuracy: {ok}/{total} = {rate:.1%}  (need ≥{threshold:.0%})")
    for m in misses:
        print("  MISS", m)
    assert rate >= threshold, (
        f"品类映射准确率 {rate:.1%} < 85% ({ok}/{total}); misses={misses}"
    )


# ═══════════════════════════════════════ AT-M2-03 ═══════════════════════════


def test_at_m2_03_b2b_hard_reject():
    """全部 B2B 反例被硬拒绝: 无 niche_key、clarification_questions 非空."""
    ideas = _load_ideas()
    b2b = [e for e in ideas if e.get("reject_reason") == "b2b"]
    assert len(b2b) >= 3, f"黄金集需 ≥3 条 B2B 反例, 实际 {len(b2b)}"

    for e in b2b:
        g = _ground_idea(e["idea_text"])
        assert g.rejected, f"B2B 例未被拒绝: {e['idea_text'][:30]}"
        assert g.niche_key is None, f"B2B 例不应产出 niche_key: {g.niche_key}"
        assert g.clarification_questions, "硬拒绝必须返回非空 clarification_questions"
        assert g.reject_reason == "b2b", f"reject_reason 应为 b2b, 实际 {g.reject_reason}"


# ═══════════════════════════════════════ AT-M2-04 ═══════════════════════════


def test_at_m2_04_confidence_gate_semantics(monkeypatch):
    """置信度闸门: <0.55 硬拒绝、>=0.55 通过 (边界 0.55 含入)."""
    import oransim.spec.ground as gm

    # 用一个 synonyms 必命中的 spec (美妆面膜), bus=None → coverage 1.0、factor 1.0,
    # 故 confidence == _SYNONYM_BASE_CONF, 直接操纵 base 跨越阈值边界。
    idea = "一款保湿面膜，定价 49 元，小红书美妆博主种草。"

    def _conf_with_base(base: float):
        monkeypatch.setattr(gm, "_SYNONYM_BASE_CONF", base)
        return _ground_idea(idea)

    g054 = _conf_with_base(0.54)
    assert g054.rejected, "confidence 0.54 < 0.55 必须硬拒绝"
    assert g054.niche_key is None
    assert g054.clarification_questions

    g055 = _conf_with_base(0.55)
    assert not g055.rejected, "confidence 0.55 == 阈值, 含入应通过"
    assert g055.niche_key is not None

    g056 = _conf_with_base(0.56)
    assert not g056.rejected, "confidence 0.56 > 0.55 应通过"
    assert g056.niche_key is not None


# ═══════════════════════════════════════ AT-M2-05 ═══════════════════════════


def test_at_m2_05_ueb_dual_source_registered(api_client):
    """_bootstrap_index() 后 BUS 含 product_categories + category_notes 且可检索."""
    from oransim.runtime.embedding_bus import BUS

    sources = {s["source"] for s in BUS.list_sources()}
    assert "product_categories" in sources, "缺少 product_categories UEB 源"
    assert "category_notes" in sources, "缺少 category_notes UEB 源"

    # 两源各检索一次, 断言返回非空
    for src in ("product_categories", "category_notes"):
        rec = BUS._sources[src]
        qvec = rec.embedder.embed("beauty::美妆 口红 护肤")
        hits = BUS.search(qvec, src, top_k=3)
        assert hits, f"源 {src} 检索返回空"
        # item 形如 "niche::caption", 可解析 niche
        item = hits[0]["item"]
        assert isinstance(item, str) and "::" in item, f"{src} item 编码异常: {item!r}"


# ═══════════════════════════════════════ AT-M2-06 ═══════════════════════════


def test_at_m2_06_corpus_coverage_lowers_confidence():
    """grounded niche 在 category_notes 无覆盖 → 置信度下降并可触发硬拒绝."""
    from oransim.config import niches
    from oransim.runtime.embedding_bus import EmbeddingBus, HashTextEmbedder

    caps = niches.bias_captions()
    keys = niches.niche_keys()
    excluded = "pet"  # 故意不给 pet 建语料覆盖
    assert excluded in keys

    bus = EmbeddingBus()
    bus.register("category_notes", HashTextEmbedder(seed_offset=41))
    covered = [k for k in keys if k != excluded]
    bus.index("category_notes", [f"{k}::{caps.get(k, k)}" for k in covered])

    # 覆盖 niche (beauty): 置信度高、不拒绝
    g_cov = _ground_idea("一款保湿面膜，定价 49 元，小红书美妆博主种草。", bus=bus)
    # 无覆盖 niche (pet): synonyms 命中 pet, 但语料零覆盖 → 置信度被惩罚
    g_unc = _ground_idea("一款猫厕所自动清洁器，售价 1299 元，小红书宠物博主合作。", bus=bus)

    assert g_unc.grounding_confidence < g_cov.grounding_confidence, (
        f"无覆盖 niche 置信度 {g_unc.grounding_confidence} 应低于有覆盖 {g_cov.grounding_confidence}"
    )
    assert not g_cov.rejected, "有语料覆盖的 niche 不应被拒绝"
    assert g_unc.rejected, "零语料覆盖应触发硬拒绝"
    assert g_unc.grounding_confidence < 0.55


# ═══════════════════════════════════════ AT-M2-07 ═══════════════════════════


def test_at_m2_07_synonyms_priority_over_embedding(monkeypatch):
    """关键词命中时不走嵌入兜底路径 (确定性优先): _embed_fallback 调用计数 = 0."""
    import oransim.spec.ground as gm

    calls = {"n": 0}
    orig = gm._embed_fallback

    def _spy(spec, bus):
        calls["n"] += 1
        return orig(spec, bus)

    monkeypatch.setattr(gm, "_embed_fallback", _spy)

    # 含明确 synonyms 关键词 (面膜/美妆) 的文本 → 必走关键词分支
    g = _ground_idea("一款保湿面膜，定价 49 元，小红书美妆博主种草。")
    assert not g.rejected and g.niche_key == "beauty"
    assert calls["n"] == 0, f"关键词命中却调用了嵌入兜底 {calls['n']} 次 (应为 0)"
