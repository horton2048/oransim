"""一次性: 抓一份真实 /api/launch/simulate 输出, 冻存成前端开发的地基 fixture.

照 tests/conftest.py::api_client 的方式起 TestClient (mock 模式, 确定性 POP/SOUL),
ingest 金标 idea -> simulate -> 把真实 LaunchReport 落 replay-viz/fixtures/launch_sample.json.

用法:  .venv\Scripts\python.exe replay-viz\scripts\capture_launch_sample.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

os.environ["LLM_MODE"] = "mock"
os.environ["PYTHONHASHSEED"] = "0"
os.environ["POP_SIZE"] = "2000"      # _GOLDEN_POP_SIZE
os.environ["SOUL_POOL_N"] = "5"      # _GOLDEN_SOUL_POOL

_GOLD_IDEA = "一款保湿面膜，定价 89 元，小红书美妆博主种草。"

from fastapi.testclient import TestClient  # noqa: E402
from oransim import api  # noqa: E402

with TestClient(api.app, raise_server_exceptions=True) as client:
    ing = client.post("/api/launch/ingest", json={"idea_text": _GOLD_IDEA, "locale": "zh-CN"})
    ing.raise_for_status()
    spec_id = ing.json()["spec_id"]
    assert spec_id, f"ingest 未产出 spec_id: {ing.text}"

    sim = client.post("/api/launch/simulate", json={"spec_id": spec_id})
    sim.raise_for_status()
    report = sim.json()

out = REPO / "replay-viz" / "fixtures" / "launch_sample.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

# 顶层结构速览, 打到 stdout
def _shape(v, depth=0):
    if isinstance(v, dict):
        return {k: _shape(x, depth + 1) for k, x in v.items()} if depth < 2 else f"<dict:{len(v)}keys>"
    if isinstance(v, list):
        head = _shape(v[0], depth + 1) if v else None
        return f"<list[{len(v)}] of {head}>"
    return type(v).__name__

print(f"WROTE {out}  ({out.stat().st_size} bytes)")
print(json.dumps(_shape(report), ensure_ascii=False, indent=2))
