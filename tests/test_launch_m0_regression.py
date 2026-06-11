"""M0 — 回归地基 (launch-sim backend).

上游: docs/plans/2026-06-11-launch-acceptance-test-cases.md §1
铁律 4: M0 前置于一切。这三件套 (AT-M0-01/02/03) 必须先入库且绿,
之后任何功能代码才允许合入。

AT-M0-01  hash 反射回归         — Scenario 每个字段要么进 hash 要么在冻结白名单
AT-M0-02  /api/predict 黄金快照  — campaign 路径字节级兼容 (铁律 1)
AT-M0-03  scale_kpi 乘法不变量   — revenue 随 conversions 等比缩放
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import numpy as np  # noqa: E402

# ======================================================== AT-M0-01 反射回归

# 冻结白名单: 这四个字段当前不进 hash_tuple()。白名单是「事实陈述」不是「许可」——
# 只许减不许增。新增任何 Scenario 字段时, 反射测试会强制你要么把它加进 hash,
# 要么显式扩这里 (而第 4 步的子集断言会挡住非法扩容)。
# 依据: 方案 §4.1; 规范 §3.3、§8.2-1。
FROZEN_HASH_EXEMPT = frozenset(
    {
        "macro_ctr_lift",
        "macro_cvr_lift",
        "cross_platform_overlap",
        "llm_calibration",
    }
)


def _base_creative(cid: str = "m0-base"):
    from oransim.data.creatives import make_creative

    return make_creative(creative_id=cid, caption="m0 reflection probe", duration_sec=15.0)


def _kol(kid: str):
    from oransim.data.kols import KOL

    return KOL(
        id=kid,
        name=kid,
        platform="douyin",
        fan_count=100_000,
        interaction_rate=0.05,
        price_cny=5_000,
        niche="beauty",
        emb=np.zeros(64, dtype=np.float64),
    )


# 每个字段的 (值A, 值B): A 进 base, B 是变体。两者仅该字段不同。
# audience_filter 走 id() 语义, 单独断言, 不进此表。
_SHARED_CREATIVE = None  # 同一对象, 保证非 creative 字段变体里 creative.id 不变


def _field_variants():
    """field name -> (value_a, value_b) 仅该字段不同的一对取值。"""
    cre_a = _base_creative("m0-cre-a")
    cre_b = _base_creative("m0-cre-b")  # 不同 id
    return {
        "creative": (cre_a, cre_b),
        "total_budget": (5_000.0, 7_000.0),
        "platform_alloc": ({"douyin": 0.6, "xhs": 0.4}, {"douyin": 0.3, "xhs": 0.7}),
        "kol_per_platform": ({"douyin": _kol("k-a")}, {"douyin": _kol("k-b")}),
        "seed": (0, 99),
        # 白名单四字段: 变体应不改 hash
        "macro_ctr_lift": (1.0, 3.0),
        "macro_cvr_lift": (1.0, 3.0),
        "cross_platform_overlap": (0.0, 0.9),
        "llm_calibration": (None, 0.7),
    }


def _make_scenario(**overrides):
    from oransim.causal.counterfactual import Scenario

    global _SHARED_CREATIVE
    if _SHARED_CREATIVE is None:
        _SHARED_CREATIVE = _base_creative("m0-shared")
    base = dict(
        creative=_SHARED_CREATIVE,
        total_budget=5_000.0,
        platform_alloc={"douyin": 0.6, "xhs": 0.4},
        audience_filter=None,
        kol_per_platform=None,
        seed=0,
        macro_ctr_lift=1.0,
        macro_cvr_lift=1.0,
        cross_platform_overlap=0.0,
        llm_calibration=None,
    )
    base.update(overrides)
    return Scenario(**base)


def test_at_m0_01_hash_reflection():
    """每个 Scenario 字段要么影响 hash_tuple(), 要么在冻结白名单中。

    这是反射测试: 它枚举 dataclasses.fields(Scenario), 任何新增字段若既不进
    hash 也未登记变体, 都会让本测试红 —— 强制「先红后绿」。
    """
    from oransim.causal.counterfactual import Scenario

    variants = _field_variants()

    # 步骤 4 (先做): 测试内白名单 ⊆ 冻结集 —— 只许减不许增。
    assert FROZEN_HASH_EXEMPT <= frozenset(
        {"macro_ctr_lift", "macro_cvr_lift", "cross_platform_overlap", "llm_calibration"}
    ), "冻结白名单被扩容 —— 新字段不许免 hash"

    # 步骤 1-3: 枚举全部字段。
    for f in dataclasses.fields(Scenario):
        name = f.name
        if name == "audience_filter":
            continue  # 特例: id() 语义单独断言 (见下)

        assert name in variants, (
            f"Scenario 新增了字段 '{name}' 但未在反射测试中登记变体。"
            f" 请在 _field_variants() 加一对取值, 并确认该字段已进 hash_tuple() "
            f"或显式加入 FROZEN_HASH_EXEMPT (后者会被子集断言挡住非法扩容)。"
        )

        val_a, val_b = variants[name]
        s_a = _make_scenario(**{name: val_a})
        s_b = _make_scenario(**{name: val_b})

        if name in FROZEN_HASH_EXEMPT:
            assert s_a.hash_tuple() == s_b.hash_tuple(), (
                f"白名单字段 '{name}' 不应进 hash, 但改它却改变了 hash_tuple()"
            )
        else:
            assert s_a.hash_tuple() != s_b.hash_tuple(), (
                f"非白名单字段 '{name}' 必须影响 hash_tuple(), 但改它 hash 没变 —— "
                f"要么把它加进 hash, 要么 (经评审) 加进冻结白名单。"
            )


# ==================================================== AT-M0-02 黄金快照

GOLDEN_DIR = Path(__file__).parent / "golden"

# 三组固定 payload: 单平台 / 多平台 / 带 competitors。
# today 冻结为 2026-01-15, 防止节气/季节因子随日期漂移。
# n_souls 设 5 确保测试快; lifecycle_days=14; 全部 extras 关闭。
# 依据: 铁律 1 (字节级兼容); 规范 §8.2-2.
_PREDICT_PAYLOADS: dict[str, dict] = {
    "single": {
        "creative": {"caption": "m0-golden-single-v1"},
        "total_budget": 50000,
        "platform_alloc": {"douyin": 1.0},
        "today": "2026-01-15",
        "n_souls": 5,
        "lifecycle_days": 14,
        "enable_crossplat": False,
        "enable_discourse": False,
        "enable_brand_memory": False,
        "enable_recsys_rl": False,
        "enable_groupchat": False,
        "use_llm": False,
    },
    "multi": {
        "creative": {"caption": "m0-golden-multi-v1"},
        "total_budget": 80000,
        "platform_alloc": {"douyin": 0.6, "xhs": 0.4},
        "today": "2026-01-15",
        "n_souls": 5,
        "lifecycle_days": 14,
        "enable_crossplat": False,
        "enable_discourse": False,
        "enable_brand_memory": False,
        "enable_recsys_rl": False,
        "enable_groupchat": False,
        "use_llm": False,
    },
    "competitors": {
        "creative": {"caption": "m0-golden-competitors-v1"},
        "total_budget": 60000,
        "platform_alloc": {"douyin": 0.5, "xhs": 0.5},
        "competitors": ["rival_a", "rival_b"],
        "today": "2026-01-15",
        "n_souls": 5,
        "lifecycle_days": 14,
        "enable_crossplat": False,
        "enable_discourse": False,
        "enable_brand_memory": False,
        "enable_recsys_rl": False,
        "enable_groupchat": False,
        "use_llm": False,
    },
}


def _extract_json_bytes(raw: bytes) -> bytes:
    """Strip streaming whitespace keepalive preamble, return raw JSON bytes."""
    import json

    stripped = raw.lstrip(b" \n\r\t")
    json.loads(stripped)  # validate parseable
    return stripped


# Keys whose values are volatile (UUIDs, timestamps, run metadata).
# Normalizing these before snapshot comparison means we protect KPI values and
# response structure (the real regression risk) without false-failing on
# ephemeral IDs.  Decision: DECISIONS.md 2026-06-11 AT-M0-02 schema_outputs.
_VOLATILE_KEYS = frozenset(
    {
        "fit_id", "run_id", "plan_id", "prediction_id", "diffusion_id",
        "simulation_id", "metric_id", "sensitivity_id", "report_id",
        "comparison_id", "estimation_id", "elasticity_id",
        "run_timestamp", "fetched_at", "generated_at",
    }
)


def _normalize(obj):
    """Recursively replace volatile fields with a stable sentinel."""
    if isinstance(obj, dict):
        return {
            k: ("<normalized>" if k in _VOLATILE_KEYS else _normalize(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    return obj


def _call_predict(client, payload: dict) -> bytes:
    import json

    resp = client.post("/api/predict", json=payload)
    assert resp.status_code == 200, f"/api/predict {resp.status_code}: {resp.text[:200]}"
    raw = _extract_json_bytes(resp.content)
    # Normalize volatile metadata then re-serialize deterministically.
    normalized = _normalize(json.loads(raw))
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def test_at_m0_02_golden_snapshot(api_client):
    """campaign 路径字节级兼容 — 铁律 1 的可执行形式。

    首次运行: golden 文件不存在 → 生成并入库 (bootstrap)。
    后续运行: 与入库文件字节级比对, 任何差异即失败。

    禁止「顺手更新快照」— 快照变更必须单独说明并引用方案修订 (铁律 1 红线)。
    依据: 规范 §8.2-2。
    api_client fixture (conftest.py) 确保 bootstrap 在整个 session 只跑一次。
    """
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    mismatches: list[str] = []
    for name, payload in _PREDICT_PAYLOADS.items():
        golden_path = GOLDEN_DIR / f"predict_snap_{name}.json"
        actual = _call_predict(api_client, payload)

        if not golden_path.exists():
            golden_path.write_bytes(actual)
            print(f"  [bootstrap] wrote {golden_path.name} ({len(actual)} bytes)")
            continue

        expected = golden_path.read_bytes()
        if actual != expected:
            mismatches.append(
                f"payload '{name}': golden mismatch "
                f"(expected {len(expected)}B, got {len(actual)}B). "
                f"NEVER silently update — file a plan-level PR instead."
            )

    assert not mismatches, "\n".join(mismatches)


def test_at_m0_01_audience_filter_id_semantics():
    """audience_filter 按 id() 语义入 hash: 同一对象 → 同 hash; 不同对象 (即便内容相等) → 不同 hash。

    该语义被 M3 的 intern 依赖, 禁止改。依据: 规范 §3.3。
    """
    from oransim.platforms.xhs.world_model_legacy import AudienceFilter

    af1 = AudienceFilter(age_buckets=[1, 2], gender=0)
    af2 = AudienceFilter(age_buckets=[1, 2], gender=0)  # 内容相等, 不同对象

    # 同一对象用于两个 Scenario → hash 相同
    s_same_1 = _make_scenario(audience_filter=af1)
    s_same_2 = _make_scenario(audience_filter=af1)
    assert s_same_1.hash_tuple() == s_same_2.hash_tuple()

    # 不同对象 (即便内容相等) → hash 不同 (id() 语义)
    s_other = _make_scenario(audience_filter=af2)
    assert s_same_1.hash_tuple() != s_other.hash_tuple()


# ==================================================== AT-M0-03 scale_kpi 乘法不变量


def test_at_m0_03_scale_kpi_revenue_conversions_ratio(api_client):
    """revenue 随 conversions 等比缩放 —— 隐含单价 (AOV) 在预算调整后不变。

    通过 sandbox session API 触发 fast_approx 分支 (仅 total_budget 变化时走此路径),
    断言 revenue/conversions 比值在缩放前后保持不变 (rel_tol=1e-6)。
    依据: 方案 §4.7 (v1.2); 规范 §3.4-1; engine.py:192。
    api_client fixture (conftest.py) 确保 bootstrap 在整个 session 只跑一次。
    """
    import math

    create_payload = {
        "creative": {"caption": "m0-scalekpi-probe-v1"},
        "total_budget": 50000,
        "platform_alloc": {"douyin": 0.6, "xhs": 0.4},
        "today": "2026-01-15",
        "n_souls": 3,
        "lifecycle_days": 14,
        "enable_crossplat": False,
        "enable_discourse": False,
        "enable_brand_memory": False,
        "enable_recsys_rl": False,
        "enable_groupchat": False,
        "use_llm": False,
    }

    r_create = api_client.post("/api/sandbox/session", json=create_payload)
    assert r_create.status_code == 200, r_create.text
    sess = r_create.json()
    sid = sess["id"]

    # 仅改预算 → 应走 fast_approx 分支
    r_patch = api_client.patch(
        f"/api/sandbox/session/{sid}", json={"total_budget": 100000}
    )
    assert r_patch.status_code == 200, r_patch.text
    sess_after = r_patch.json()

    assert sess_after.get("mode") == "fast_approx", (
        f"expected fast_approx, got {sess_after.get('mode')!r} — "
        "budget-only patch must not trigger a full rerun"
    )

    kpis_before = sess["baseline_kpis"]   # baseline == current at session creation
    kpis_after = sess_after["current_kpis"]

    rev_b = kpis_before.get("revenue", 0)
    conv_b = kpis_before.get("conversions", 0)
    rev_a = kpis_after.get("revenue", 0)
    conv_a = kpis_after.get("conversions", 0)

    # 需要两个 KPI 都非零才能测比值
    assert conv_b > 0, "baseline conversions == 0 — cannot test ratio invariant"
    assert conv_a > 0, "scaled conversions == 0 — fast_approx broke"

    aov_before = rev_b / conv_b
    aov_after = rev_a / conv_a
    assert math.isclose(aov_before, aov_after, rel_tol=1e-6), (
        f"scale_kpi broke AOV invariant: before={aov_before:.4f}, after={aov_after:.4f}. "
        "engine.py:192 'revenue = conversions x AOV (AOV unchanged)' violated."
    )


def test_at_m0_03_scale_kpi_invariant_comment_present():
    """engine.py 内有 AOV 不变量注释 (流程断言)。

    注释是「不变量已落地」的唯一证明; 没注释 = 隐性知识, 容易被后来者覆盖。
    依据: 规范 §3.4-1 流程断言。
    """
    engine_py = Path(__file__).parent.parent / "backend" / "oransim" / "sandbox" / "engine.py"
    assert engine_py.exists(), f"engine.py not found at {engine_py}"
    content = engine_py.read_text(encoding="utf-8")
    assert "revenue = conversions" in content and "AOV" in content, (
        "engine.py 缺少 AOV 不变量注释 (形如 'revenue = conversions × AOV (AOV 不变)')。"
        " 请在 scale_kpi 定义旁补上。"
    )
