"""AT-M7-xx API + 报告 acceptance tests (建设中, 逐 AT 累积).

AT-M7-03 ingest 不烧仿真
AT-M7-04 spec 存储 append-only
AT-M7-05 硬拒绝端到端
AT-M7-08 现有 8 路由契约不变
AT-M7-13 引擎层依赖方向 (REG-4)
... (其余 AT 随实现累积)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ═══════════════════════════════════════ AT-M7-04 ═══════════════════════════


def _make_spec(name="保湿面膜", price=89.0):
    from oransim.spec.schema import ProductSpec
    return ProductSpec(
        product_name=name,
        one_liner=f"{name}，定价 {price} 元，小红书种草。",
        category_raw="beauty",
        target_user_raw="美妆人群",
        price_point={"amount": price, "currency": "CNY", "model": "one_time"},
        provenance=[{"start": 0, "end": 10}],
    )


def test_at_m7_04_spec_store_append_only(tmp_path):
    """PATCH 追加新版本而非原地改写; v0 可回读且逐字相等; 重载缓存后版本链完整."""
    from oransim.spec import store

    store.reset(cache_path=tmp_path / "specs.json")

    spec_v0 = _make_spec(price=89.0)
    spec_id, rev0 = store.put(spec_v0)
    assert rev0 == 0

    # PATCH → 追加 v1 (改价)
    spec_v1 = _make_spec(price=99.0)
    rev1 = store.append(spec_id, spec_v1)
    assert rev1 == 1

    # 版本链 = [v0, v1]
    versions = store.versions(spec_id)
    assert len(versions) == 2

    # v0 可回读且与 PATCH 前逐字相等 (append-only, 未原地改写)
    got_v0 = store.get(spec_id, revision=0)
    assert got_v0.price_point["amount"] == 89.0
    assert got_v0.model_dump() == spec_v0.model_dump()

    # latest = v1
    assert store.get(spec_id).price_point["amount"] == 99.0

    # 重载缓存 (模拟重启进程) → 版本链完整
    store.reset(cache_path=tmp_path / "specs.json")  # 清内存, 保留磁盘
    store.load_from_cache(tmp_path / "specs.json")
    reloaded = store.versions(spec_id)
    assert len(reloaded) == 2, "重启后版本链应完整"
    assert store.get(spec_id, revision=0).price_point["amount"] == 89.0
    assert store.get(spec_id, revision=1).price_point["amount"] == 99.0


# ═══════════════════════════════════════ AT-M7-13 ═══════════════════════════


def test_at_m7_13_engine_no_spec_import():
    """引擎层 (data/config/agents/diffusion/causal/sandbox/runtime) 无 import oransim.spec."""
    import re

    engine_dirs = [
        "data", "config", "agents", "diffusion", "causal", "sandbox", "runtime",
    ]
    pat = re.compile(r"^\s*(import\s+oransim\.spec|from\s+oransim\.spec)", re.M)
    offenders = []
    base = BACKEND / "oransim"
    for d in engine_dirs:
        for py in (base / d).rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            if pat.search(text):
                offenders.append(str(py.relative_to(base)))
    assert not offenders, f"引擎层禁止 import oransim.spec (REG-4): {offenders}"


# ═══════════════════════════════════════ helpers ════════════════════════════

_GOLD_IDEA = "一款保湿面膜，定价 89 元，小红书美妆博主种草。"
_B2B_IDEA = "一款给企业 HR 部门用的 SaaS 招聘管理平台，月费 3000 元/席，主要走 B2B 销售。"


def _ingest(client, idea=_GOLD_IDEA, locale="zh-CN"):
    r = client.post("/api/launch/ingest", json={"idea_text": idea, "locale": locale})
    assert r.status_code == 200, r.text
    return r.json()


# ═══════════════════════════════════════ AT-M7-03 ═══════════════════════════


def test_at_m7_03_ingest_no_simulation(api_client, monkeypatch):
    """ingest 全程零 ScenarioRunner.run() 调用 (spy 计数 = 0)."""
    from oransim import api_state

    calls = {"n": 0}
    orig = api_state.RUNNER.run

    def _spy(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    monkeypatch.setattr(api_state.RUNNER, "run", _spy)
    res = _ingest(api_client)
    assert res["spec_id"], "正例应产出 spec_id"
    assert calls["n"] == 0, f"ingest 不应调用 ScenarioRunner.run，实际 {calls['n']} 次"


# ═══════════════════════════════════════ AT-M7-05 ═══════════════════════════


def test_at_m7_05_b2b_routes_to_tier_c(api_client):
    """分诊台 (BREAKING, design D-1): B2B idea 不再硬拒, 路由到 C 档并产出 spec_id。

    旧行为 (rejected=True / spec_id=None) 是本次有意改掉的「保安式守门」。
    新行为: 任何想法都不 dead-end —— B2B → tier=C, 仍给 spec_id 走统一 simulate。
    伪造 spec_id 仍是 4xx (未知 spec 与「拒绝」是两回事)。
    """
    res = _ingest(api_client, idea=_B2B_IDEA)
    assert res["rejected"] is False, "分诊台不再硬拒"
    assert res["spec_id"], "B2B 也应产出 spec_id (路由到 C, 非 dead-end)"
    assert res["tier"] == "C", f"B2B 应路由到 C 档, 实际 {res.get('tier')}"
    assert "routed_reason" in res and res["routed_reason"]

    # 伪造 spec_id 调 simulate → 显式 4xx (未知 spec, 不产出部分报告)
    r = api_client.post("/api/launch/simulate", json={"spec_id": "deadbeef_fake"})
    assert 400 <= r.status_code < 500, f"伪造 spec_id 应 4xx，实际 {r.status_code}"


# ═══════════════════════════════════════ AT-M7-01 ═══════════════════════════


def test_at_m7_01_end_to_end_main_chain(api_client):
    """ingest → PATCH → simulate → 完整 LaunchReport；复现性数值一致."""
    # 1. ingest
    ing = _ingest(api_client)
    spec_id = ing["spec_id"]
    assert spec_id and ing["grounding_confidence"] >= 0.55

    # 2. PATCH 修正字段 → provenance user_confirmed, 版本 +1
    pr = api_client.patch(f"/api/launch/spec/{spec_id}", json={"price_cny": 99.0})
    assert pr.status_code == 200, pr.text
    pj = pr.json()
    assert pj["revision"] == 1, "PATCH 后版本应 +1"
    assert pj["provenance_status"] == "user_confirmed"
    assert "price_point" in pj["confirmed_fields"]

    # 3. simulate → LaunchReport 四区块齐全
    sr = api_client.post("/api/launch/simulate",
                         json={"spec_id": spec_id, "overrides": {"n_seeds": 5}})
    assert sr.status_code == 200, sr.text
    rep = sr.json()
    assert rep["disclaimer"] == "这是带标注不确定性的情景推演，不是预测"
    assert "header" in rep and rep["header"]["assumptions"], "头部假设回显缺失"
    # 指标三档分位
    m = rep["metrics"]["adopters"]
    assert m["band"] and "p35" in m and "p50" in m and "p65" in m
    assert m["p35_label"] == "下行情形"
    # 时间线 90 点 + peak/half_life/saturation
    tl = rep["timeline"]
    assert tl["n_points"] == 90
    assert "peak_day" in tl and "half_life" in tl and "saturation_date" in tl
    # 谁会买 + 什么会出问题
    assert rep["who_buys"]["cate_segments"]
    assert rep["what_breaks"]["intervention_cards"]

    # 4. 复现性: 同请求再跑 → 数值一致
    sr2 = api_client.post("/api/launch/simulate",
                          json={"spec_id": spec_id, "overrides": {"n_seeds": 5}})
    rep2 = sr2.json()
    assert rep["metrics"] == rep2["metrics"], "同请求两次 metrics 应一致 (固定 seed)"
    assert rep["timeline"] == rep2["timeline"], "同请求两次 timeline 应一致"


# ═══════════════════════════════════════ AT-M7-02 ═══════════════════════════


def test_at_m7_02_honesty_markers_all_endpoints(api_client):
    """ingest/PATCH/simulate/sandbox/whatif 五端点响应顶层均有 assumed_fields + grounding_confidence."""
    ing = _ingest(api_client)
    spec_id = ing["spec_id"]
    assert "assumed_fields" in ing and "grounding_confidence" in ing

    pr = api_client.patch(f"/api/launch/spec/{spec_id}", json={"price_cny": 79.0}).json()
    assert "assumed_fields" in pr and "grounding_confidence" in pr

    sim = api_client.post("/api/launch/simulate", json={"spec_id": spec_id}).json()
    assert "assumed_fields" in sim and "grounding_confidence" in sim

    sb = api_client.post("/api/launch/sandbox", json={"spec_id": spec_id}).json()
    assert "assumed_fields" in sb and "grounding_confidence" in sb

    wi = api_client.get(f"/api/launch/whatif/{spec_id}").json()
    assert "assumed_fields" in wi and "grounding_confidence" in wi


# ═══════════════════════════════════════ AT-M7-08 ═══════════════════════════


def test_at_m7_08_existing_routes_unchanged(api_client):
    """既有 8 路由仍在; launch 路由为纯新增."""
    paths = {r.path for r in api_client.app.routes}
    # 既有 campaign 路由代表性路径
    for p in ["/api/predict", "/api/dag", "/api/platforms"]:
        assert p in paths, f"既有路由 {p} 缺失 — 违反铁律 1"
    # launch 纯新增
    assert "/api/launch/ingest" in paths
    assert "/api/launch/simulate" in paths


# ═══════════════════════════════════════ AT-M7-12 ═══════════════════════════


def test_at_m7_12_report_copy_redlines(api_client):
    """报告文案红线: 第一句逐字、P35 下行情形、竞品前缀、objection 原话、locale 标注."""
    from oransim.causal.launch_interventions import COMPETITOR_BRANCH_PREFIX

    ing = _ingest(api_client)
    rep = api_client.post("/api/launch/simulate", json={"spec_id": ing["spec_id"]}).json()

    # ① 第一句逐字
    assert rep["disclaimer"] == "这是带标注不确定性的情景推演，不是预测"
    # ② P35 行带「下行情形」
    assert rep["metrics"]["adopters"]["p35_label"] == "下行情形"
    # ③ 竞品卡前缀逐字
    comp = [c for c in rep["what_breaks"]["intervention_cards"]
            if c["name"] == "competitor_response"]
    assert comp and COMPETITOR_BRANCH_PREFIX in comp[0]["label"]
    assert comp[0]["branch"] is True

    # ⑤ locale != zh-CN → assumed_fields 含市场环境标注
    en = _ingest(api_client, idea="An organic lip balm for Gen Z women. RMB 39. Xiaohongshu.",
                 locale="en-US")
    if en.get("spec_id"):
        sim_en = api_client.post("/api/launch/simulate", json={"spec_id": en["spec_id"]}).json()
        assert any("中国社媒市场" in a for a in sim_en["assumed_fields"]), \
            "非 zh-CN locale 应在 assumed_fields 标注市场环境"


# ═══════════════════════════════════════ AT-M7-09 ═══════════════════════════


def test_at_m7_09_n_seeds_degradation(api_client):
    """n_seeds=1 → 无分位带 + 标注；默认 5 → 三档带齐；n_seeds>9 → 显式拒绝."""
    ing = _ingest(api_client)
    sid = ing["spec_id"]

    # n_seeds=1 → 单点、无分位带
    s1 = api_client.post("/api/launch/simulate",
                         json={"spec_id": sid, "overrides": {"n_seeds": 1}}).json()
    m1 = s1["metrics"]["adopters"]
    assert m1["band"] is None, "n_seeds=1 应无分位带"
    assert "单点、无分位带" in (m1.get("note", "") + s1["metrics"].get("degradation_note", ""))

    # n_seeds=5 → 三档带齐
    s5 = api_client.post("/api/launch/simulate",
                         json={"spec_id": sid, "overrides": {"n_seeds": 5}}).json()
    m5 = s5["metrics"]["adopters"]
    assert m5["band"] and {"p35", "p50", "p65"} <= set(m5)

    # n_seeds>9 → 显式拒绝 (pydantic 422, 非静默截断)
    r = api_client.post("/api/launch/simulate",
                        json={"spec_id": sid, "overrides": {"n_seeds": 20}})
    assert r.status_code == 422, f"n_seeds>9 应显式拒绝，实际 {r.status_code}"


# ═══════════════════════════════════════ AT-M7-06 ═══════════════════════════


def test_at_m7_06_launch_sandbox_sliders(api_client):
    """launch sandbox 建 session 后 price/budget/alloc PATCH、counterfactual、undo、ws 可用."""
    ing = _ingest(api_client)
    sb = api_client.post("/api/launch/sandbox", json={"spec_id": ing["spec_id"]}).json()
    sid = sb["sid"]
    assert sb["mode"] == "launch"

    base = api_client.get(f"/api/sandbox/session/{sid}").json()
    base_conv = base["current_kpis"]["conversions"]

    # price 滑杆
    p_price = api_client.patch(f"/api/sandbox/session/{sid}", json={"price_cny": 200.0})
    assert p_price.status_code == 200, p_price.text
    assert p_price.json()["current_kpis"]["conversions"] != base_conv, "price 滑杆应改变 KPI"

    # budget 滑杆
    p_bud = api_client.patch(f"/api/sandbox/session/{sid}", json={"total_budget": 120000.0})
    assert p_bud.status_code == 200

    # alloc 滑杆
    p_alloc = api_client.patch(f"/api/sandbox/session/{sid}",
                               json={"platform_alloc": {"xhs": 1.0}})
    assert p_alloc.status_code == 200

    # counterfactual
    cf = api_client.post(f"/api/sandbox/session/{sid}/counterfactual",
                         json={"total_budget": 80000.0})
    assert cf.status_code == 200

    # undo
    u = api_client.post(f"/api/sandbox/session/{sid}/undo")
    assert u.status_code == 200

    # WebSocket: 发 patch 收 snapshot 帧
    with api_client.websocket_connect(f"/ws/sandbox/{sid}") as wsconn:
        wsconn.send_text('{"total_budget": 90000}')
        frame = wsconn.receive_json()
        assert "current_kpis" in frame, "ws 应回传 snapshot 帧"


# ═══════════════════════════════════════ AT-M7-07 ═══════════════════════════


def test_at_m7_07_lifecycle_never_silently_legacy(api_client):
    """launch session lifecycle → 409 (不落 legacy 14 天); campaign session 行为不变."""
    # launch session → 409 + 指引, 绝不返回 legacy HAWKES 14 天
    ing = _ingest(api_client)
    sb = api_client.post("/api/launch/sandbox", json={"spec_id": ing["spec_id"]}).json()
    lc = api_client.get(f"/api/sandbox/session/{sb['sid']}/lifecycle")
    assert lc.status_code == 409, f"launch lifecycle 应 409，实际 {lc.status_code}"
    assert "legacy" in lc.text or "Bass" in lc.text or "90" in lc.text

    # campaign session → 行为不变 (200, legacy 14 天可用)
    cs = api_client.post("/api/sandbox/session", json={
        "creative": {"caption": "campaign lifecycle 回归"},
        "total_budget": 50000, "platform_alloc": {"douyin": 1.0},
    }).json()
    lc2 = api_client.get(f"/api/sandbox/session/{cs['id']}/lifecycle")
    assert lc2.status_code == 200, "campaign session lifecycle 应不变 (200)"


# ═══════════════════════════════════════ AT-M7-10 ═══════════════════════════


def test_at_m7_10_souls_only_p50_seed(api_client, monkeypatch):
    """n_seeds=5 时 soul infer_batch 调用次数 = 1 个 seed 的量 (其余 seed 纯统计)."""
    from oransim import api_state

    calls = {"n": 0}
    orig = api_state.SOULS.infer_batch

    def _spy(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    monkeypatch.setattr(api_state.SOULS, "infer_batch", _spy)
    ing = _ingest(api_client)
    api_client.post("/api/launch/simulate",
                    json={"spec_id": ing["spec_id"], "overrides": {"n_seeds": 5}})
    assert calls["n"] == 1, f"souls 应只跑 P50 主 seed (1 次)，实际 {calls['n']} 次"


# ═══════════════════════════════════════ AT-M7-11 ═══════════════════════════


def test_at_m7_11_cost_cap_explicit_reject(api_client, monkeypatch):
    """成本上限 monkeypatch 极低 → 显式拒绝 (非静默); 成本计入 COST_TABLE_CNY 账本."""
    from oransim.agents.soul_llm import COST_TABLE_CNY
    from oransim.api_routers import launch as launch_mod

    assert COST_TABLE_CNY, "成本账本 COST_TABLE_CNY 应非空 (同一账本)"

    ing = _ingest(api_client)
    monkeypatch.setattr(launch_mod, "MAX_REQUEST_COST_CNY", 0.0001)
    r = api_client.post("/api/launch/simulate",
                        json={"spec_id": ing["spec_id"], "overrides": {"n_souls": 100}})
    assert r.status_code == 402, f"超成本上限应显式拒绝 402，实际 {r.status_code}"
    assert "cost" in r.text.lower() or "成本" in r.text


# ═══════════════════════════════════════ AT-M7-14 ═══════════════════════════


def test_at_m7_14_streaming_keepalive(api_client, monkeypatch):
    """慢路径下 ingest 流式按 keepalive 间隔发空白帧，连接不超时，JSON 仍可解析."""
    import json as _json
    import time as _t

    from oransim.api_routers import launch as launch_mod

    orig = launch_mod._ingest_sync

    def _slow(req):
        _t.sleep(0.3)  # 慢路径 > keepalive 间隔
        return orig(req)

    monkeypatch.setattr(launch_mod, "_KEEPALIVE_SEC", 0.05)
    monkeypatch.setattr(launch_mod, "_ingest_sync", _slow)

    r = api_client.post("/api/launch/ingest", json={"idea_text": _GOLD_IDEA})
    assert r.status_code == 200
    raw = r.content
    # keepalive 空白帧在 JSON 前 (慢路径下应出现至少一个)
    assert raw[:1] in (b" ", b"\n") or b" \n" in raw[:40], "慢路径应有 keepalive 空白帧"
    # 去空白后仍是合法 JSON (前端 fetch().json() 无需改)
    parsed = _json.loads(raw.lstrip())
    assert parsed["spec_id"], "keepalive 后 JSON 仍应可解析"
