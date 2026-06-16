"""结构化人群定向 (launch C 端) — audience overrides 真实改变 KPI + 可复现。

FE-M6 后端增量: SimulateOverrides 加 audience_age_buckets/gender/city_tiers,
经 compile_spec(audience_override) → AudienceFilter → 世界模型 _audience_score 重加权人群。
"""
from __future__ import annotations

_GOLD = "一款保湿面膜，定价 89 元，小红书美妆博主种草。"


def _ingest(c, idea=_GOLD):
    r = c.post("/api/launch/ingest", json={"idea_text": idea, "locale": "zh-CN"})
    assert r.status_code == 200, r.text
    return r.json()["spec_id"]


def _kpis(c, spec_id, overrides):
    r = c.post("/api/launch/simulate", json={"spec_id": spec_id, "overrides": overrides})
    assert r.status_code == 200, r.text
    m = r.json()["metrics"]
    return (m["unique_reach"]["p50"], m["adopters"]["p50"], m["revenue"]["p50"])


def test_audience_gender_changes_kpis(api_client):
    sid = _ingest(api_client)
    female = _kpis(api_client, sid, {"audience_gender": 0})
    male = _kpis(api_client, sid, {"audience_gender": 1})
    assert female != male, f"性别定向应改变 KPI: F={female} M={male}"


def test_audience_age_changes_kpis(api_client):
    sid = _ingest(api_client)
    young = _kpis(api_client, sid, {"audience_age_buckets": [0, 1]})
    old = _kpis(api_client, sid, {"audience_age_buckets": [4, 5]})
    assert young != old, f"年龄定向应改变 KPI: young={young} old={old}"


def test_audience_override_reproducible(api_client):
    sid = _ingest(api_client)
    a = _kpis(api_client, sid, {"audience_gender": 1})
    b = _kpis(api_client, sid, {"audience_gender": 1})
    assert a == b, f"同定向应可复现: {a} vs {b}"


def test_no_override_unchanged(api_client):
    """不给 audience override → 与之前行为一致 (基线可跑、可复现)。"""
    sid = _ingest(api_client)
    a = _kpis(api_client, sid, {})
    b = _kpis(api_client, sid, {})
    assert a == b
