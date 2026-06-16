"""soul_infer_llm_launch — launch 版真 LLM soul 的字段映射 (曾因 campaign/launch 字段
错位导致 objection/would_pay 丢空)。stub 掉 provider, 断言映射 + 强制规范化 + 错误路径。
"""

from __future__ import annotations

import types

from oransim.agents import soul_llm


class _StubResult:
    def __init__(self, content):
        self.content = content
        self.usage = {"prompt_tokens": 10, "completion_tokens": 20}
        self.latency_ms = 123
        self.raw_preview = content[:50]


class _StubProvider:
    def __init__(self, content):
        self._content = content

    def generate(self, **kwargs):
        return _StubResult(self._content)


def _persona():
    p = types.SimpleNamespace(interests=["咖啡", "家居"])
    p.full_card = lambda: "28岁女，上海，爱精致生活"
    return p


def _patch(monkeypatch, content):
    monkeypatch.setattr(soul_llm, "get_provider", lambda: _StubProvider(content))
    monkeypatch.setattr(soul_llm, "resolve_provider_name", lambda: "openai")


def test_launch_soul_maps_launch_fields(monkeypatch):
    _patch(
        monkeypatch,
        '{"will_try": true, "would_pay_cny": 199, '
        '"objection": "怕太复杂", "purchase_intent_7d": 0.7}',
    )
    r = soul_llm.soul_infer_llm_launch(_persona(), caption="咖啡套装上市", platform="xhs")
    assert r["will_try"] is True
    assert r["would_pay_cny"] == 199.0
    assert r["objection"] == "怕太复杂"
    assert r["purchase_intent_7d"] == 0.7
    # 没有 campaign 字段泄漏
    assert "will_click" not in r


def test_launch_soul_coerces_messy_values(monkeypatch):
    # 金额带单位、意向越界、objection 缺失 → 规范化
    _patch(
        monkeypatch, '{"will_try": "yes", "would_pay_cny": "¥299元", ' '"purchase_intent_7d": 1.8}'
    )
    r = soul_llm.soul_infer_llm_launch(_persona(), caption="x", platform="xhs")
    assert r["would_pay_cny"] == 299.0
    assert r["purchase_intent_7d"] == 1.0  # clamp 到 [0,1]
    assert r["objection"] == ""  # 缺失 → 空串, 不报错


def test_launch_soul_bad_json_returns_error(monkeypatch):
    # 非 JSON (无花括号) → _error, 交由 infer_batch 走 mock-fallback
    _patch(monkeypatch, "抱歉我无法回答")
    r = soul_llm.soul_infer_llm_launch(_persona(), caption="x", platform="xhs")
    assert "_error" in r
