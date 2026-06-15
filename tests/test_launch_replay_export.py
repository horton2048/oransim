"""AT-FE-1-xx · 上市回放适配器 launch_replay_export 验收 (全自动, 确定性).

规范: replay-viz/design/launch/02-验收规范.md (FE-M1)
被测: replay-viz/launch_replay_export.py::export(report) -> replay.json v1
地基: replay-viz/fixtures/launch_sample.json (真实 LaunchReport, 由 scripts/capture_launch_sample.py 抓取)

先红后绿: 适配器未实现时全部 FAIL。落 tests/ (禁 backend/tests/), mock 无关 (纯数据变换)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
REPLAY_VIZ = REPO / "replay-viz"
FIXTURE = REPLAY_VIZ / "fixtures" / "launch_sample.json"
GOLDEN = REPLAY_VIZ / "fixtures" / "launch_replay.golden.json"

if str(REPLAY_VIZ) not in sys.path:
    sys.path.insert(0, str(REPLAY_VIZ))


def _export_fn():
    """惰性导入被测 export(); 未实现时给出清晰 red。"""
    try:
        import launch_replay_export  # type: ignore
    except ImportError as e:
        pytest.fail(f"launch_replay_export 尚未实现 (FE-M1 先红): {e}")
    assert hasattr(launch_replay_export, "export"), "模块需暴露纯函数 export(report)->dict"
    return launch_replay_export.export


def _report() -> dict:
    assert FIXTURE.exists(), f"地基样本缺失 {FIXTURE} — 先跑 scripts/capture_launch_sample.py"
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def report() -> dict:
    return _report()


@pytest.fixture()
def out(report) -> dict:
    return _export_fn()(report)


# ── validReplay 的 Python 镜像 (app/v3-final.html::validReplay 等价物) ──────────
def _valid_replay(j: dict) -> bool:
    def arr(k):
        return isinstance(j.get(k), list) and len(j[k]) > 0

    fp = j.get("funnel_percentiles")
    return bool(
        j
        and j.get("version") == 1
        and j.get("kpis")
        and isinstance(j.get("budget"), (int, float))
        and arr("cities")
        and arr("daily_total")
        and isinstance(j.get("kols"), list)
        and isinstance(j.get("souls"), list)
        and fp
        and fp.get("A1_awareness")
        and fp.get("A3_engagement")
        and fp.get("A4_conversion")
        and j.get("per_platform")
    )


_TIER_LABEL = {1: "T1", 2: "T2", 3: "T3", 4: "T4", 5: "T5+"}


# ═══════════════════════════════ AT-FE-1-01 ═════════════════════════════════
def test_at_fe_1_01_deterministic(report):
    """同输入连跑 2 次输出逐字节相同。"""
    exp = _export_fn()
    a = json.dumps(exp(report), ensure_ascii=False, sort_keys=True)
    b = json.dumps(exp(json.loads(json.dumps(report))), ensure_ascii=False, sort_keys=True)
    assert a == b, "export 非确定性: 两次输出不一致"


# ═══════════════════════════════ AT-FE-1-02 ═════════════════════════════════
def test_at_fe_1_02_golden(out):
    """export() 输出 == 冻存黄金 (逐字节)。"""
    assert GOLDEN.exists(), (
        f"黄金缺失 {GOLDEN} — 适配器实现后由其产出, 人工核对再冻存 (绝不在循环里顺手重生)"
    )
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert out == golden, "输出与黄金不一致 (逐字节比对失败)"


# ═══════════════════════════════ AT-FE-1-03 ═════════════════════════════════
def test_at_fe_1_03_passes_valid_replay(out):
    """输出满足 v3 validReplay() 形状校验 (否则 v3 拒绝加载、回退内嵌)。"""
    assert _valid_replay(out), f"未过 validReplay: keys={sorted(out.keys())}"


# ═══════════════════════════════ AT-FE-1-04 ═════════════════════════════════
def test_at_fe_1_04_spine_untouched(out, report):
    """脊柱真值不被篡改: daily_total 逐点 == timeline.daily_adopters; peak_day 一致。"""
    assert out["daily_total"] == report["timeline"]["daily_adopters"], (
        "daily_total 被平滑/裁剪/补值/重排 — 违诚实红线"
    )
    assert out["meta"]["peak_day"] == report["timeline"]["peak_day"]


# ═══════════════════════════════ AT-FE-1-05 ═════════════════════════════════
def test_at_fe_1_05_metrics_passthrough(out, report):
    """metrics 原样附带, 各指标 p35<=p50<=p65 不倒挂。"""
    assert out.get("metrics") == report["metrics"], "metrics 未原样直通"
    for name, band in report["metrics"].items():
        if isinstance(band, dict) and "p35" in band:
            assert band["p35"] <= band["p50"] <= band["p65"], f"{name} 分位倒挂"


# ═══════════════════════════════ AT-FE-1-06 ═════════════════════════════════
def test_at_fe_1_06_intervention_cards_verbatim(out, report):
    """干预卡逐字段直通, note 逐字不润色。"""
    src = report["what_breaks"]["intervention_cards"]
    assert out.get("intervention_cards") == src, "intervention_cards 未逐字段直通"
    for c in out["intervention_cards"]:
        assert set(c) >= {"name", "label", "delta", "branch", "note"}


# ═══════════════════════════════ AT-FE-1-07 ═════════════════════════════════
def test_at_fe_1_07_synthetic_marked(out):
    """所有合成字段在 meta.synthetic_fields 声明。"""
    sf = " ".join(out["meta"].get("synthetic_fields", []))
    for token in ("cities", "souls", "t"):
        assert token in sf, f"合成项 {token!r} 未在 meta.synthetic_fields 声明"
    # 合成城市须带整体标记
    assert any(c.get("name") for c in out["cities"]), "cities 为空"


# ═══════════════════════════════ AT-FE-1-08 ═════════════════════════════════
def test_at_fe_1_08_city_tier_truth(out, report):
    """各 tier 的 Σweight 占比 == effective_city_dist (误差<0.5pt); 未命中进 unmapped_cities。"""
    dist = report["who_buys"]["cate_segments"][0]["summary"]["effective_city_dist"]
    tw: dict[int, float] = {}
    for c in out["cities"]:
        tw[c["tier"]] = tw.get(c["tier"], 0.0) + c["weight"]
    total = sum(tw.values())
    assert total > 0, "城市权重总和为 0"
    for tier, w in tw.items():
        label = _TIER_LABEL[tier]
        expected = dist.get(label, 0.0) / 100.0
        got = w / total
        assert abs(got - expected) < 0.005, (
            f"{label} 占比 {got:.3f} 偏离真值 {expected:.3f} (>0.5pt)"
        )
    assert isinstance(out.get("unmapped_cities"), list)


# ═══════════════════════════════ AT-FE-1-09 ═════════════════════════════════
def test_at_fe_1_09_quotes_verbatim(out, report):
    """souls[].text 用 objection 原话逐字 (非空时)。"""
    objections = {
        q["objection"].strip()
        for q in report["who_buys"]["persona_quotes"]
        if q.get("objection", "").strip()
    }
    texts = {s.get("text", "").strip() for s in out["souls"]}
    missing = objections - texts
    assert not missing, f"objection 原话未逐字进 souls.text: {missing}"


# ═══════════════════════════════ AT-FE-1-10 ═════════════════════════════════
def test_at_fe_1_10_sentiment_derivation(out):
    """souls[].sentiment 按 purchase_intent_7d 分档: >=0.5→1, <=0.05→-1, else 0。"""
    for s in out["souls"]:
        pi = s.get("purchase_intent_7d")
        if pi is None:
            continue
        want = 1 if pi >= 0.5 else (-1 if pi <= 0.05 else 0)
        assert s.get("sentiment") == want, (
            f"sentiment 派生错: intent={pi} 应 {want} 实 {s.get('sentiment')}"
        )


# ═══════════════════════════════ AT-FE-1-11 ═════════════════════════════════
def test_at_fe_1_11_honesty_meta(out, report):
    """诚实元上屏可用: meta.disclaimer == 报告原句 + grounding_confidence。"""
    assert out["meta"].get("disclaimer") == report["disclaimer"]
    assert out["meta"].get("grounding_confidence") == report["grounding_confidence"]


# ═══════════════════════════════ AT-FE-1-12 ═════════════════════════════════
def test_at_fe_1_12_synthesis_stable(report):
    """合成的 souls[].t / city 在同输入下逐字节稳定。"""
    exp = _export_fn()
    a = exp(report)
    b = exp(json.loads(json.dumps(report)))
    sa = [(s.get("t"), s.get("city")) for s in a["souls"]]
    sb = [(s.get("t"), s.get("city")) for s in b["souls"]]
    assert sa == sb, "合成的 t/city 不稳定"


# ═══════════════════════════════ AT-FE-4-02 ═════════════════════════════════
def test_at_fe_4_02_replay_route_e2e(api_client):
    """GET /api/launch/replay/{spec_id} 复用 export() 产出有效 launch replay.json。

    R5: store 持 spec, 报告由 _simulate_sync 确定性重建。证明后端路由=转换唯一源、可贯通。
    """
    idea = "一款保湿面膜，定价 89 元，小红书美妆博主种草。"
    ing = api_client.post("/api/launch/ingest", json={"idea_text": idea, "locale": "zh-CN"})
    assert ing.status_code == 200, ing.text
    spec_id = ing.json()["spec_id"]
    assert spec_id, "ingest 应产出 spec_id"

    r = api_client.get(f"/api/launch/replay/{spec_id}")
    assert r.status_code == 200, r.text
    out = r.json()
    assert _valid_replay(out), f"route 输出未过 validReplay: {sorted(out.keys())}"
    assert out["metrics"]["adopters"].get("p35") is not None, "缺 launch metrics 真值带"
    assert out["cities"] and out["daily_total"] and out["intervention_cards"]
    assert out["meta"].get("synthetic_fields"), "缺合成字段声明"

    # 未知 spec_id → 404 (非静默/非 500)
    assert api_client.get("/api/launch/replay/deadbeef_nope").status_code == 404


# ═══════════════════════════════ D15 (打包/适配器解析) ═══════════════════════
def test_d15_adapter_path_resolution(api_client, monkeypatch, tmp_path):
    """D15: 适配器路径可经 OSIM_REPLAY_VIZ_DIR 配置；找不到时显式 500 而非 ImportError 崩。"""
    idea = "一款保湿面膜，定价 89 元，小红书美妆博主种草。"
    spec_id = api_client.post(
        "/api/launch/ingest", json={"idea_text": idea, "locale": "zh-CN"}
    ).json()["spec_id"]

    # 显式配置指向真实 replay-viz → 正常 200
    monkeypatch.setenv("OSIM_REPLAY_VIZ_DIR", str(REPLAY_VIZ))
    assert api_client.get(f"/api/launch/replay/{spec_id}").status_code == 200

    # 指向不含适配器的目录 → 显式 500，报错含变量名 (可诊断)
    monkeypatch.setenv("OSIM_REPLAY_VIZ_DIR", str(tmp_path))
    r = api_client.get(f"/api/launch/replay/{spec_id}")
    assert r.status_code == 500
    assert "OSIM_REPLAY_VIZ_DIR" in r.text
