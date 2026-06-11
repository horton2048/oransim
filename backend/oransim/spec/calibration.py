"""spec/calibration.py — 标定可追溯 (方案 §5-6, 规范 §8.4, AT-M8-03).

诚实原则 (铁律 2): 当前先验全部来自合成数据自标定, 非真实校准。本模块为每个
niche 产出一条「标定 trace」: 记录标定前 (fallback 默认) → 标定后 (niches.json
v2 字段 / 仍为默认) 的分位带变化, 落盘对照, 并对未标定项显式标注。

来源标注逐字: 「合成数据自标定，非真实校准」(规范 §10 诚实红线)。

依赖方向: spec/ → config (引擎)。不被引擎层反向 import (REG-4)。
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

from oransim.config import niches as _niches

# 来源标注 (逐字红线)
CALIBRATION_SOURCE = "合成数据自标定，非真实校准（synthetic self-calibration, not real）"

_RECORD_PATH = Path("/tmp/oransim_calibration_trace.json")


def _quantile_band(reference_price: float, adoption_rate: float, bass: dict) -> dict:
    """由先验导出一个可对照的「分位带」摘要 (标定前后对比用的固定派生量)。

    用 reference_price × adoption_rate × Bass p/q 折算一个三档带 (P35/P50/P65),
    纯确定性, 仅作标定前后变化的可追溯对照, 非真实预测。
    """
    base = reference_price * adoption_rate
    spread = 0.25 + bass.get("q", 0.38)  # q 越大扩散越快, 带越宽
    return {
        "p35": round(base * (1 - spread * 0.5), 4),
        "p50": round(base, 4),
        "p65": round(base * (1 + spread * 0.5), 4),
    }


def calibration_trace(niche: str, *, record_path: str | Path | None = None) -> dict:
    """单 niche 标定 trace: before (默认先验) → after (当前 niches.json 先验)。

    - before: 强制走 fallback 默认 (未标定起点)。
    - after:  当前 getter 值 (niches.json v2 有字段则为标定值, 否则仍是默认)。
    - uncalibrated: after 是否仍来自默认 (niches.json 缺字段)。
    - source: 合成自标定标注 (诚实红线)。
    并把 trace 落盘到 record_path (before/after 对照基线)。
    """
    rp_map, rp_unc = _niches.reference_prices()
    ap_map, ap_unc = _niches.adoption_priors()
    bp_map, bp_unc = _niches.bass_priors()

    # before = 纯 fallback 默认 (标定起点)
    before_rp = _niches._REFERENCE_PRICE_FALLBACK.get(niche, 45.0)
    before_ar = _niches._ADOPTION_RATE_FALLBACK.get(niche, 0.06)
    before_bass = {"p": _niches._BASS_PRIOR_FALLBACK[0], "q": _niches._BASS_PRIOR_FALLBACK[1]}

    # after = 当前 getter (niches.json v2 字段优先)
    after_rp = rp_map.get(niche, before_rp)
    after_ar = ap_map.get(niche, before_ar)
    after_bass = bp_map.get(niche, before_bass)

    uncalibrated = niche in (rp_unc | ap_unc | bp_unc)

    before = _quantile_band(before_rp, before_ar, before_bass)
    after = _quantile_band(after_rp, after_ar, after_bass)

    trace = {
        "niche": niche,
        "before": before,
        "after": after,
        "uncalibrated": uncalibrated,
        "source": CALIBRATION_SOURCE,
        "before_priors": {"reference_price": before_rp, "adoption_rate": before_ar,
                          "bass": before_bass},
        "after_priors": {"reference_price": after_rp, "adoption_rate": after_ar,
                         "bass": after_bass},
    }

    path = Path(record_path) if record_path is not None else _RECORD_PATH
    _append_record(path, niche, trace)
    trace["record_path"] = str(path)
    return trace


def _append_record(path: Path, niche: str, trace: dict) -> None:
    """落盘 before/after 对照 (append-only by niche; 失败静默)。"""
    with contextlib.suppress(Exception):
        existing = {}
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        existing[niche] = {k: trace[k] for k in ("before", "after", "uncalibrated", "source")}
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def calibration_report_all() -> dict:
    """全品类标定 trace 汇总 (报告用; 未标定项显式标注)。"""
    out = {}
    for niche in _niches.niche_keys(include_v2=True):
        out[niche] = calibration_trace(niche)
    return out
