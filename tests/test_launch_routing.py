"""分诊台路由 + 三档信封 (idea-intake-routing / tiered-prediction / honest labeling)。

灵魂: 任何想法都不硬拒, 按 ground 信号分流 A/B/C。
  - A: 有 fan_prior 校准的消费垂类 (面膜→beauty)
  - B: 消费品但无校准 prior (气泡水→beverage), 标「未校准」+ 拉宽区间
  - C: 引擎演不了 (B2B/线下/新物种), LLM 定性情景, **无点值 KPI**; LLM 不可用→显式降级

mock 模式跑数据线; C 档 LLM 映射用桩 provider (仿 test_launch_soul_llm)。
"""

from __future__ import annotations

from oransim.agents import launch_scenario_llm as scen
from oransim.spec.ground import GroundingResult
from oransim.spec.route import resolve_prior_niche, route_idea

# ═══════════════════════════ 单元: route_idea / 别名 ═══════════════════════════


def _g(niche, rejected=False, reason=None, conf=0.9):
    return GroundingResult(
        niche_key=niche,
        grounding_confidence=conf,
        rejected=rejected,
        reject_reason=reason,
    )


def test_route_calibrated_niche_tier_a():
    for n in ("beauty", "fashion", "food", "fitness", "travel", "electronics", "parenting"):
        assert route_idea(_g(n)) == "A", n


def test_route_uncalibrated_consumer_tier_b():
    for n in ("beverage", "home", "pet"):
        assert route_idea(_g(n)) == "B", n


def test_route_rejected_tier_c():
    assert route_idea(_g(None, rejected=True, reason="b2b")) == "C"
    assert route_idea(_g(None, rejected=True, reason="unsupported_vertical")) == "C"


def test_alias_resolves_prior_tier_a():
    # electronics→tech, parenting→mom 让 A 档真用上校准 prior (否则退化 base-pop)
    assert resolve_prior_niche(_g("electronics")) == "tech"
    assert resolve_prior_niche(_g("parenting")) == "mom"
    assert resolve_prior_niche(_g("beauty")) == "beauty"
    # B / C 档不解析 (None)
    assert resolve_prior_niche(_g("beverage")) is None
    assert resolve_prior_niche(_g(None, rejected=True)) is None


def test_routing_is_reproducible():
    g = _g("beauty")
    assert route_idea(g) == route_idea(g) == "A"


# ═══════════════════════════ C 档: LLM 映射 + 无 KPI ═══════════════════════════


class _StubResult:
    def __init__(self, content):
        self.content = content
        self.usage = {"prompt_tokens": 10, "completion_tokens": 40}
        self.latency_ms = 99


class _StubProvider:
    def __init__(self, content):
        self._c = content

    def generate(self, **kw):
        return _StubResult(self._c)


_C_JSON = (
    '{"market_sizing": {"range_low": 200000000, "range_high": 2000000000, '
    '"unit": "CNY / 年", "basis": "厂数×渗透×客单"}, '
    '"buyer_personas": [{"who":"厂长","jobs_to_be_done":"降人力","willingness":"看ROI","objection":"老师傅排了二十年"}], '
    '"channels": [{"channel":"行业展会","fit":"高"},{"channel":"线上投放","fit":"低——决策人不在这买"}], '
    '"adoption_shape": {"shape":"长导入期+滞后S曲线","narrative":"前期极慢，标杆出现后陡峭放量"}, '
    '"key_risks": ["交付重","数据脏","人治惯性","账期长"]}'
)


def _patch_llm(monkeypatch, content):
    monkeypatch.setattr(scen, "llm_available", lambda: True)
    monkeypatch.setattr(scen, "get_provider", lambda: _StubProvider(content))


def _spec_dict():
    return {
        "product_name": "AI 智能排产 SaaS",
        "one_liner": "工厂排产换算法",
        "category_raw": "B2B 工业软件",
        "target_user_raw": "中小制造厂",
        "price_point": {"amount": None, "model": "per_seat"},
        "channels_hint": ["行业展会"],
        "fields": {},
        "provenance": [],
    }


def test_c_scenario_maps_fields_and_has_no_kpi(monkeypatch):
    _patch_llm(monkeypatch, _C_JSON)
    rep = scen.build_scenario_report(
        spec_dict=_spec_dict(),
        idea_text="给中小厂的 AI 排产 SaaS",
        routed_reason="b2b",
        assumed_fields=[],
    )
    assert rep["tier"] == "C"
    assert rep["no_kpi"] is True and rep["degraded"] is False
    # 红线: 绝无点值 KPI 分位带
    assert "metrics" not in rep and "timeline" not in rep
    sc = rep["scenario"]
    assert sc["market_sizing"]["magnitude_only"] is True
    assert sc["market_sizing"]["range_low"] == 200000000
    assert sc["adoption_shape"]["no_numbers"] is True
    assert sc["buyer_personas"][0]["objection"] == "老师傅排了二十年"  # 逐字不润色
    assert len(sc["channels"]) == 2 and sc["key_risks"]


def test_c_degrades_explicitly_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(scen, "llm_available", lambda: False)
    rep = scen.build_scenario_report(
        spec_dict=_spec_dict(),
        idea_text="某 B2B SaaS",
        routed_reason="b2b",
        assumed_fields=[],
    )
    assert rep["tier"] == "C" and rep["degraded"] is True
    assert rep["scenario"] is None  # 不静默造占位
    assert rep["degrade_note"] and "metrics" not in rep


def test_c_bad_json_degrades_not_crashes(monkeypatch):
    _patch_llm(monkeypatch, "抱歉，无法生成")
    rep = scen.build_scenario_report(
        spec_dict=_spec_dict(),
        idea_text="x",
        routed_reason="b2b",
        assumed_fields=[],
    )
    assert rep["degraded"] is True and rep["scenario"] is None


# ═══════════════════════════ E2E: ingest 分诊 + simulate 信封 ═════════════════

_IDEA_A = "一款保湿面膜，定价 89 元，小红书美妆博主种草。"
_IDEA_B = "一款无糖气泡水，定价 6 元/瓶，便利店铺货 + 小红书种草。"
_IDEA_C = "一款给中小制造厂的 AI 智能排产 SaaS，按工位月费，主要走 B2B 销售。"


def _ingest(client, idea):
    r = client.post("/api/launch/ingest", json={"idea_text": idea, "locale": "zh-CN"})
    assert r.status_code == 200, r.text
    return r.json()


def test_e2e_ingest_routes_three_tiers(api_client):
    a = _ingest(api_client, _IDEA_A)
    b = _ingest(api_client, _IDEA_B)
    c = _ingest(api_client, _IDEA_C)
    assert a["tier"] == "A" and b["tier"] == "B" and c["tier"] == "C"
    # 永不 dead-end: 三档都有 spec_id
    for r in (a, b, c):
        assert r["spec_id"] and r["rejected"] is False
        assert r["tier_label"] and r["routed_reason"]


def test_e2e_b_tier_band_widened_and_uncalibrated(api_client):
    b = _ingest(api_client, _IDEA_B)
    rep = api_client.post(
        "/api/launch/simulate",
        json={"spec_id": b["spec_id"], "overrides": {"n_seeds": 3, "n_souls": 8}},
    ).json()
    assert rep["tier"] == "B" and rep.get("uncalibrated") is True
    assert rep["metrics"].get("band_widened") is True
    # 至少一个指标真的被放宽了 (band_widen_factor 标记在)
    widened = [v for v in rep["metrics"].values() if isinstance(v, dict) and v.get("band_widened")]
    assert widened, "B 档应至少放宽一个分位带指标"


def test_e2e_c_tier_simulate_no_kpi_mockmode(api_client):
    """mock 模式 (无真 LLM) → C 档 simulate 显式降级, 仍无伪精确 KPI。"""
    c = _ingest(api_client, _IDEA_C)
    rep = api_client.post("/api/launch/simulate", json={"spec_id": c["spec_id"]}).json()
    assert rep["tier"] == "C" and rep["no_kpi"] is True
    assert "metrics" not in rep and "timeline" not in rep
    assert rep["degraded"] is True  # mock 模式无 LLM → 降级 (CI 默认)


def test_e2e_c_tier_replay_and_whatif_guarded_not_crash(api_client):
    """C 档无沙盘/无精确反事实: replay + whatif 显式 422 (不崩、不产伪精确 KPI)。"""
    c = _ingest(api_client, _IDEA_C)
    sid = c["spec_id"]
    r_replay = api_client.get(f"/api/launch/replay/{sid}")
    assert r_replay.status_code == 422, f"C 档 replay 应 422, 实际 {r_replay.status_code}"
    r_whatif = api_client.get(f"/api/launch/whatif/{sid}")
    assert r_whatif.status_code == 422, f"C 档 whatif 应 422, 实际 {r_whatif.status_code}"


def test_e2e_a_tier_replay_still_works(api_client):
    """回归: A 档 replay 仍出真城市回放 (未被 C 档守卫误伤)。"""
    a = _ingest(api_client, _IDEA_A)
    r = api_client.get(f"/api/launch/replay/{a['spec_id']}")
    assert r.status_code == 200, r.text
