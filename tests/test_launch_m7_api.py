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
