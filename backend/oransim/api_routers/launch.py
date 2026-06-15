"""api_routers/launch.py — 上市模拟 API (方案 §6, M7). 纯新增, 不碰 campaign 面。

端点:
  POST  /api/launch/ingest        — 抽取 + grounding (不烧仿真); 流式 keepalive
  PATCH /api/launch/spec/{id}     — 字段级修正 (人在回路确认闸, provenance→user_confirmed)
  POST  /api/launch/simulate      — 编译 → run → souls(launch) → diffusion → LaunchReport; 流式
  POST  /api/launch/sandbox       — 建 mode=launch session (复用 SandboxStore)
  GET   /api/launch/whatif/{id}   — 命名反事实弹药库 (launch_interventions)

每个响应顶层携带 assumed_fields + grounding_confidence (诚实标记红线)。
"""
from __future__ import annotations

import asyncio
import json
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .. import api_state
from ..agents.launch_outputs import NON_ZH_LOCALE_NOTE, build_launch_report
from ..api_schemas import (
    IdeaIngestRequest,
    SandboxCreateRequest,
    SimulateRequest,
    SpecPatchRequest,
)

router = APIRouter(tags=["launch"])

# 硬拒绝置信度阈值 (与 spec/ground 一致)
_REJECT_NOTE = "置信度不足或非消费垂类 — 无可模拟 spec_id"

# 单请求成本上限 (CNY)。超限显式拒绝, 非静默截断 (规范 §4, AT-M7-11)。
# 测试可 monkeypatch 本模块属性到极低值触发拒绝。
MAX_REQUEST_COST_CNY = 100.0
# 流式 keepalive 间隔秒 (默认 10; 测试可经 env 调小验证慢路径 keepalive 帧)。
_KEEPALIVE_SEC = float(os.environ.get("LAUNCH_KEEPALIVE_SEC", "10"))


def _projected_cost_cny(n_souls: int, n_seeds: int) -> float:
    """投射本请求 LLM 成本 (souls 仅 P50 主 seed; 走 COST_TABLE_CNY 同一账本)。"""
    from ..agents.soul_llm import estimate_cost_cny
    # 每 persona 估 ~250 in / ~150 out token (仅主 seed 跑 souls)
    tin = max(0, int(n_souls)) * 250
    tout = max(0, int(n_souls)) * 150
    return estimate_cost_cny(tin, tout)


def _ground_dict(g) -> dict:
    return {
        "niche_key": g.niche_key,
        "grounding_confidence": g.grounding_confidence,
        "matched_synonyms": g.matched_synonyms,
        "corpus_coverage": g.corpus_coverage,
    }


def _ingest_sync(req: IdeaIngestRequest) -> dict:
    from ..spec import store
    from ..spec.extract import extract_spec
    from ..spec.ground import ground
    from ..spec.normalize import normalize_spec

    spec = normalize_spec(extract_spec(req.idea_text))
    g = ground(spec)

    assumed = list(spec.assumed_fields)
    if req.locale != "zh-CN" and NON_ZH_LOCALE_NOTE not in assumed:
        assumed.append(NON_ZH_LOCALE_NOTE)

    if g.rejected:
        # 硬拒绝: 无 spec_id, clarification 非空 (规范 §6.2)
        return {
            "spec_id": None,
            "spec": None,
            "assumed_fields": assumed,
            "grounding_confidence": g.grounding_confidence,
            "grounding": _ground_dict(g),
            "clarification_questions": g.clarification_questions,
            "rejected": True,
            "note": _REJECT_NOTE,
        }

    spec_id, _rev = store.put(spec, locale=req.locale)
    return {
        "spec_id": spec_id,
        "spec": spec.model_dump(),
        "assumed_fields": assumed,
        "grounding_confidence": g.grounding_confidence,
        "grounding": _ground_dict(g),
        "clarification_questions": [],
        "rejected": False,
    }


def _stream_json(sync_fn, *args):
    """predict.py 同款 10s keepalive 流式包装。"""
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(None, sync_fn, *args)

    async def gen():
        while not fut.done():
            try:
                await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(fut)),
                                       timeout=_KEEPALIVE_SEC)
            except asyncio.TimeoutError:
                yield b" \n"  # keepalive whitespace; JSON parser ignores
        result = fut.result()
        yield json.dumps(result, ensure_ascii=False, default=str).encode("utf-8")

    return StreamingResponse(gen(), media_type="application/json")


@router.post("/api/launch/ingest")
async def launch_ingest(req: IdeaIngestRequest):
    """抽取 + grounding，不烧仿真 (廉价预览闸)。流式 keepalive。"""
    return _stream_json(_ingest_sync, req)


@router.patch("/api/launch/spec/{spec_id}")
async def launch_spec_patch(spec_id: str, req: SpecPatchRequest):
    """字段级修正: provenance→user_confirmed, 追加新版本, 重算 grounding。"""
    from ..spec import store
    from ..spec.ground import ground
    from ..spec.normalize import normalize_spec

    if not store.exists(spec_id):
        raise HTTPException(status_code=404, detail=f"unknown spec_id {spec_id}")

    cur = store.get(spec_id)
    data = cur.model_dump()
    patch = req.model_dump(exclude_none=True)

    confirmed_fields = []
    for k, v in patch.items():
        if k == "price_cny":
            data["price_point"] = {**data.get("price_point", {}), "amount": float(v)}
            confirmed_fields.append("price_point")
        else:
            data[k] = v
            confirmed_fields.append(k)

    # 修正过的字段标 user_confirmed (人在回路确认 = 不再是 inferred/default)
    data["provenance"] = data.get("provenance") or [{"start": 0, "end": 1}]
    data["inferred"] = False
    data["default_applied"] = False
    fields_meta = dict(data.get("fields", {}))
    for f in confirmed_fields:
        fields_meta.pop(f"{f}_default", None)
        fields_meta[f] = {"value": str(data.get(f)), "inferred": False,
                          "default_applied": False, "provenance": [{"start": 0, "end": 1}]}
    data["fields"] = fields_meta

    new_spec = normalize_spec(type(cur)(**data))
    new_rev = store.append(spec_id, new_spec)
    g = ground(new_spec)

    return {
        "spec_id": spec_id,
        "revision": new_rev,
        "spec": new_spec.model_dump(),
        "assumed_fields": list(new_spec.assumed_fields),
        "grounding_confidence": g.grounding_confidence,
        "grounding": _ground_dict(g),
        "confirmed_fields": confirmed_fields,
        "provenance_status": "user_confirmed",
    }


def _simulate_sync(req: SimulateRequest) -> dict:
    from ..causal.launch_interventions import run_intervention
    from ..diffusion.bass_saturated_hawkes import (
        BassSaturatedConfig,
        BassSaturatedHawkes,
        market_potential,
    )
    from ..spec import store
    from ..spec.ground import ground
    from ..spec.pipeline import compile_spec

    spec = store.get(req.spec_id)
    g = ground(spec)
    rev = store.latest_revision(req.spec_id)
    locale = store.get_locale(req.spec_id)

    ov = req.overrides
    n_seeds = max(1, min(9, ov.n_seeds))
    seeds = list(range(42, 42 + n_seeds))

    runner = api_state.RUNNER
    kols = api_state.KOLS
    pop = api_state.POP

    # 多 seed Monte Carlo: 经验分位带 (souls 只跑 P50 主 seed — AT-M7-10)
    per_seed_kpis = []
    primary_compiled = None
    for i, sd in enumerate(seeds):
        compiled = compile_spec(spec, spec_id=req.spec_id, revision=rev, kols=kols,
                                budget_hint_cny=ov.budget, seed=sd)
        res = runner.run(compiled.scenario, n_monte_carlo=3)
        per_seed_kpis.append(res.total_kpis)
        if i == len(seeds) // 2:
            primary_compiled = compiled

    primary_compiled = primary_compiled or compiled

    # souls launch mode (仅主 seed)
    launch_personas = []
    souls = api_state.SOULS
    if souls is not None and ov.use_llm is not None:
        cre = primary_compiled.scenario.creative
        first_plat = next(iter(primary_compiled.scenario.platform_alloc))
        launch_personas = souls.infer_batch(
            cre, {}, None, first_plat, n_sample=min(8, ov.n_souls or 8),
            seed=seeds[len(seeds) // 2], use_llm=False, mode="launch",
        )

    # 90 天 diffusion timeline (Bass 饱和)
    niche = g.niche_key or "beauty"
    m = market_potential(pop, niche)
    bass = BassSaturatedHawkes(BassSaturatedConfig(horizon_days=ov.horizon_days, market_m=m))
    fc = bass.forecast([(0.0, "impression")])
    conv_idx = bass._conversion_idx()
    daily_adopters = [day[conv_idx] for day in fc.daily_buckets]
    import numpy as _np
    cum = _np.cumsum(daily_adopters)
    peak_day = int(_np.argmax(daily_adopters)) if daily_adopters else 0
    total = cum[-1] if len(cum) else 0.0
    half_life = next((d for d, c in enumerate(cum) if c >= total * 0.5), len(cum))
    saturation_date = next((d for d, c in enumerate(cum) if c >= 0.9 * m), None)
    price = float(spec.price_point.get("amount", 45.0))
    daily_revenue = [a * price for a in daily_adopters]
    timeline = {
        "daily_adopters": [round(a, 4) for a in daily_adopters],
        "daily_revenue": [round(r, 4) for r in daily_revenue],
        "n_points": len(daily_adopters),
        "peak_day": peak_day,
        "half_life": int(half_life),
        "saturation_date": saturation_date,
        "market_potential_m": round(m, 2),
        "calibrated": False,
    }

    # 区块3: 谁会买 (fan_profile 有效人群画像 + persona 引语)
    from ..data.fan_profile import fan_profile_summary
    fps = fan_profile_summary(pop, niche)
    cate_segments = [
        {"dimension": "fan_profile", "niche": niche, "summary": fps},
    ]

    # 区块4: 干预叙事卡 (含竞品分支)
    base_result = runner.run(primary_compiled.scenario, n_monte_carlo=5)
    cards = []
    for nm in ("price_up_30", "no_kol_launch", "competitor_response"):
        try:
            r = run_intervention(nm, primary_compiled.scenario, runner, base_result)
            cards.append({"name": r.name, "label": r.label, "delta": r.delta,
                          "branch": r.branch, "note": r.note})
        except Exception:
            pass

    season_window = {"note": "假日/季节因子最佳/最差上市窗口 (data/macro)",
                     "category_hint": niche}

    report = build_launch_report(
        spec_dict=spec.model_dump(),
        assumed_fields=list(spec.assumed_fields),
        grounding=_ground_dict(g) | {"grounding_confidence": g.grounding_confidence},
        per_seed_kpis=per_seed_kpis,
        launch_personas=launch_personas,
        timeline=timeline,
        cate_segments=cate_segments,
        intervention_cards=cards,
        audit_risk=float(primary_compiled.scenario.creative.audit_risk),
        season_window=season_window,
        locale=locale,
        budget_hint_cny=ov.budget,
    )
    report["spec_id"] = req.spec_id
    report["n_seeds"] = n_seeds
    return report


@router.post("/api/launch/simulate")
async def launch_simulate(req: SimulateRequest):
    """编译 → 多 seed run → souls(launch) → diffusion → LaunchReport。流式。"""
    # 校验必须在流式开始前 (流一旦开始无法转 4xx, 且硬拒绝不出部分报告 — 规范 §6.2)
    from ..spec import store

    if not req.spec_id or not store.exists(req.spec_id):
        raise HTTPException(status_code=400, detail="unknown or missing spec_id — ingest first")

    # 成本上限: 投射成本超限 → 显式 402, 非静默截断/部分结果 (规范 §4, AT-M7-11)
    projected = _projected_cost_cny(req.overrides.n_souls, req.overrides.n_seeds)
    if projected > MAX_REQUEST_COST_CNY:
        raise HTTPException(
            status_code=402,
            detail=(
                f"projected request cost ¥{projected:.4f} exceeds cap "
                f"¥{MAX_REQUEST_COST_CNY:.4f}; reduce n_souls/n_seeds or raise cap. "
                "成本计入 COST_TABLE_CNY 账本, 显式拒绝不静默截断。"
            ),
        )
    return _stream_json(_simulate_sync, req)


@router.get("/api/launch/replay/{spec_id}")
async def launch_replay(spec_id: str):
    """把 spec_id 的上市推演转成回放前端 replay.json (AT-FE-4-02)。

    复用 launch_replay_export.export() — 转换逻辑全系统唯一一份 (replay-viz/, CLI 与本路由共用)。
    R5: store 持 spec; LaunchReport 由 _simulate_sync 确定性重建, 不依赖 session 缓存报告。
    供主 SPA「战况回放」tab 的 iframe (?session=<spec_id>) 取数。
    """
    from ..spec import store

    if not store.exists(spec_id):
        raise HTTPException(status_code=404, detail=f"unknown spec_id {spec_id}")
    report = _simulate_sync(SimulateRequest(spec_id=spec_id))
    # 回放适配器在 replay-viz/ (单一转换源, D4/D15)。打包/部署解析顺序:
    #   1) OSIM_REPLAY_VIZ_DIR 显式配置  2) monorepo 默认 (仓库根/replay-viz)。
    # 找不到 → 显式 500 (不让 ImportError 崩得莫名)。
    import os
    import sys
    from pathlib import Path

    rv = os.environ.get("OSIM_REPLAY_VIZ_DIR") or str(
        Path(__file__).resolve().parents[3] / "replay-viz"
    )
    if not (Path(rv) / "launch_replay_export.py").exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"回放适配器未找到于 {rv} — 随后端一同部署 replay-viz/，"
                "或设环境变量 OSIM_REPLAY_VIZ_DIR 指向它 (D15)。"
            ),
        )
    if rv not in sys.path:
        sys.path.insert(0, rv)
    from launch_replay_export import export as _export_replay

    return _export_replay(report)


@router.post("/api/launch/sandbox")
async def launch_sandbox(req: SandboxCreateRequest):
    """用编译出的 Scenario 建 mode=launch session (复用 SandboxStore)。"""
    from ..spec import store
    from ..spec.ground import ground
    from ..spec.pipeline import compile_spec

    if not store.exists(req.spec_id):
        raise HTTPException(status_code=404, detail=f"unknown spec_id {req.spec_id}")
    spec = store.get(req.spec_id)
    g = ground(spec)
    rev = store.latest_revision(req.spec_id)
    compiled = compile_spec(spec, spec_id=req.spec_id, revision=rev, kols=api_state.KOLS, seed=42)
    sess = api_state.SANDBOX.create(compiled.scenario)
    sess.mode = "launch"  # 持久标记 launch session (lifecycle 路由据此)
    return {
        "sid": sess.id,
        "mode": "launch",
        "assumed_fields": list(spec.assumed_fields),
        "grounding_confidence": g.grounding_confidence,
    }


@router.get("/api/launch/whatif/{spec_id}")
async def launch_whatif(spec_id: str):
    """命名反事实弹药库 (launch_interventions 全跑)。"""
    from ..causal.launch_interventions import INTERVENTION_NAMES, run_intervention
    from ..spec import store
    from ..spec.ground import ground
    from ..spec.pipeline import compile_spec

    if not store.exists(spec_id):
        raise HTTPException(status_code=404, detail=f"unknown spec_id {spec_id}")
    spec = store.get(spec_id)
    g = ground(spec)
    rev = store.latest_revision(spec_id)
    compiled = compile_spec(spec, spec_id=spec_id, revision=rev, kols=api_state.KOLS, seed=42)
    base = api_state.RUNNER.run(compiled.scenario, n_monte_carlo=5)

    cards = []
    for nm in INTERVENTION_NAMES:
        try:
            r = run_intervention(nm, compiled.scenario, api_state.RUNNER, base)
            cards.append({"name": r.name, "label": r.label, "delta": r.delta,
                          "branch": r.branch, "note": r.note, "paid_events": r.paid_events})
        except Exception as e:  # noqa: BLE001
            cards.append({"name": nm, "error": str(e)})

    return {
        "spec_id": spec_id,
        "interventions": cards,
        "assumed_fields": list(spec.assumed_fields),
        "grounding_confidence": g.grounding_confidence,
    }
