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
