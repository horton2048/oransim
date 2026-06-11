"""spec/pipeline.py — 四阶段编译管线骨架 (M1 骨架, M3/M7 完善).

阶段: extract → normalize → ground (M2) → scenario_gen (M3)
规范 §3.5.
"""
from __future__ import annotations

from .extract import extract_spec
from .normalize import normalize_spec
from .schema import ProductSpec


def ingest(idea_text: str) -> ProductSpec:
    """Stage 1+2: extract + normalize (M1 deliverable)."""
    raw = extract_spec(idea_text)
    return normalize_spec(raw)
