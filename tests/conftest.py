"""Session-wide fixtures for the oransim test suite.

Provides a single bootstrapped TestClient so that api_state.bootstrap()
runs exactly once per pytest session. Multiple bootstrap() calls in the
same process can crash (numpy/C extensions in worker threads from a prior
lifespan still referencing freed objects). Tests that need the full API
should request the `api_client` fixture instead of creating their own
TestClient with lifespan.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Pin population size for the shared client so all snapshot-based tests get
# consistent byte output regardless of which env the suite runs in.
_GOLDEN_POP_SIZE = "2000"
_GOLDEN_SOUL_POOL = "5"


# ---------------------------------------------------------------------------
# live_llm marker — skip-by-default (用例集 §CI 模式). 标 @pytest.mark.live_llm
# 的用例 (AT-M2-02 / M8 live 复跑) 需真实 LLM 供应商; 无 key 时自动 skip, 保
# `LLM_MODE=mock` CI 全绿。设 LLM_MODE=api + LLM_API_KEY (或 OPENAI_API_KEY)
# 后自动启用; 或显式传 --run-live 强制收集。
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--run-live", action="store_true", default=False,
        help="强制运行 @live_llm 用例 (默认仅在检测到真实 LLM 供应商时运行)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_llm: 需真实 LLM 供应商的用例 (skip-by-default; 用 --run-live 或设 "
        "LLM_MODE=api + LLM_API_KEY 启用)",
    )


def _live_llm_available() -> bool:
    try:
        from oransim.agents.soul_llm import llm_available
        return bool(llm_available())
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live") or _live_llm_available():
        return  # 启用: 不 skip
    skip_live = pytest.mark.skip(
        reason="live_llm: 未检测到真实 LLM 供应商 (设 LLM_MODE=api + LLM_API_KEY，"
        "或传 --run-live)"
    )
    for item in items:
        if "live_llm" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(scope="session")
def api_client():
    """A session-scoped TestClient that bootstraps api_state exactly once.

    Env vars are set before the lifespan runs and restored after.
    Tests that need the HTTP API should inject this fixture rather than
    creating their own TestClient contexts.
    """
    from fastapi.testclient import TestClient
    from oransim import api

    prev_pop = os.environ.get("POP_SIZE")
    prev_souls = os.environ.get("SOUL_POOL_N")
    os.environ["POP_SIZE"] = _GOLDEN_POP_SIZE
    os.environ["SOUL_POOL_N"] = _GOLDEN_SOUL_POOL

    with TestClient(api.app, raise_server_exceptions=True) as client:
        yield client

    if prev_pop is None:
        os.environ.pop("POP_SIZE", None)
    else:
        os.environ["POP_SIZE"] = prev_pop
    if prev_souls is None:
        os.environ.pop("SOUL_POOL_N", None)
    else:
        os.environ["SOUL_POOL_N"] = prev_souls
