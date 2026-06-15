# -*- coding: utf-8 -*-
"""launch_replay_export.py — 把一次 /api/launch/simulate (LaunchReport) 转成 v3 回放所需的 replay.json v1。

规范: design/launch/01-开发规范.md。完全确定性 (无时钟、无随机)，同输入逐字节同输出。
被测: tests/test_launch_replay_export.py (AT-FE-1-01..12)。

架构 (DECISIONS D2): A 为主——本适配器把 LaunchReport 重塑成 v3 认的 campaign replay.json 形状，
缺口确定性合成 + meta.synthetic_fields 打标; 判决面板的 P35/P50/P65 真值由 v3 改读 metrics (决策 B, M3)。

诚实声明——输出里哪些是合成的 (同时汇总在 meta.synthetic_fields):
  - cities[]              launch 报告无城市块; 层级占比取自 effective_city_dist 真值，
                         坐标查内置 GAZETTEER (映射非编造)，名额按层级占比确定性分配。
  - souls[].t            persona 无 timestamp，按扩散曲线质量分布确定性合成 (t_synthetic=true)。
  - souls[].city         persona 无城市，按 effective_city_dist 加权确定性指派。
  - souls[].sentiment    persona 无情绪，按 purchase_intent_7d 确定性分档。
  - souls[].persona      niche·tier 派生短标签 (不杜撰具体人设)。
  - kols[]               launch 报告无 KOL 块，默认空 (引爆幕降级，DECISIONS D3)。
  - per_platform         按 channels_hint (真) 拆分，曝光/ROI 比例为合成。
  - funnel_percentiles   占位——判决面板已改读 metrics 真值 (DECISIONS D7)。
  - budget               launch 报告无顶层 budget，由 revenue.p50 / payback.p50 反推。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "fixtures" / "launch_sample.json"
# 默认输出与 campaign 的 app/replay.json 错开，避免 standalone 跑覆盖定稿 demo。
# M2 接 v3 时再决定最终落位 (见 design/launch/01-开发规范.md §6)。
DEFAULT_OUTPUT = HERE / "app" / "launch-replay.json"

# 复用 campaign 适配器的地名表 (坐标真值，层级口径一致)。
from replay_export import GAZETTEER, curve_time, stable_frac  # noqa: E402

_TIER_LABEL = {1: "T1", 2: "T2", 3: "T3", 4: "T4", 5: "T5+"}
_TARGET_CITIES = 25  # 铺城名额 (DECISIONS D4)


def _band35(b):
    """metrics 的 p35/p50/p65 带 → 占位 funnel 的 p25/p50/p75 槽 (DECISIONS D7)。"""
    return {"p25": b.get("p35"), "p50": b.get("p50"), "p75": b.get("p65")}


def build_cities(effective_city_dist, n_target=_TARGET_CITIES):
    """effective_city_dist (T1..T5+ 占比, 真值) + GAZETTEER → [{name,lat,lng,tier,weight}]。

    每 tier 名额 = round(N × 占比); 该 tier 内 weight = 占比 / 名额 → Σweight(tier) == 占比,
    故各层级权重占比逐字保真 (AT-FE-1-08)。坐标查 GAZETTEER。
    """
    by_tier = {}
    for name, (lat, lng, tier) in GAZETTEER.items():
        by_tier.setdefault(tier, []).append((name, lat, lng))
    for t in by_tier:
        by_tier[t].sort(key=lambda x: x[0])  # 稳定排序 (按城市名)

    cities, unmapped = [], []
    for tier in (1, 2, 3, 4, 5):
        pct = effective_city_dist.get(_TIER_LABEL[tier], 0.0)
        if pct <= 0:
            continue
        quota = round(n_target * pct / 100.0)
        if quota <= 0:
            continue
        pool = by_tier.get(tier, [])
        take = pool[:quota]
        if len(take) < quota:
            unmapped.append({"tier": _TIER_LABEL[tier],
                             "shortfall": quota - len(take)})  # GAZETTEER 该层级不足，披露非静默
        w = round(pct / len(take), 6) if take else 0.0
        for name, lat, lng in take:
            cities.append({"name": name, "lat": lat, "lng": lng,
                           "tier": tier, "weight": w})
    return cities, unmapped


def _pick_city(frac, cities):
    """[0,1) → 按 weight 加权确定性选一座城市。"""
    total = sum(c["weight"] for c in cities) or 1.0
    acc = 0.0
    for c in cities:
        acc += c["weight"] / total
        if frac < acc:
            return c
    return cities[-1]


def build_souls(persona_quotes, cities, niche, daily):
    """persona_quotes → 证词列表。objection 原话逐字; city/sentiment/t/persona 确定性合成。"""
    souls = []
    for i, q in enumerate(persona_quotes):
        objection = (q.get("objection") or "").strip()
        key = f"soul:{i}:{objection}"
        city = _pick_city(stable_frac(key), cities) if cities else {"name": "", "tier": 0}
        pi = q.get("purchase_intent_7d")
        sentiment = 0
        if pi is not None:
            sentiment = 1 if pi >= 0.5 else (-1 if pi <= 0.05 else 0)
        souls.append({
            "t": round(curve_time(stable_frac(key), daily), 2),
            "t_synthetic": True,
            "persona": f"{niche}·{_TIER_LABEL.get(city['tier'], '')}",
            "city": city["name"],
            "text": objection,  # 原话逐字，不润色 (AT-FE-1-09)
            "sentiment": sentiment,
            "will_click": bool(q.get("will_try")),
            "would_pay_cny": q.get("would_pay_cny"),
            "purchase_intent_7d": pi,
        })
    souls.sort(key=lambda s: (s["t"], s["text"]))  # t 升序; 同刻按文本稳定
    return souls


def export(report):
    """LaunchReport (dict) -> replay.json v1 (dict)。纯函数，确定性。"""
    metrics = report.get("metrics", {})
    timeline = report.get("timeline", {})
    who = report.get("who_buys", {})
    breaks = report.get("what_breaks", {})

    daily = list(timeline.get("daily_adopters", []))  # 真值，不平滑/裁剪/补值/重排
    cate = (who.get("cate_segments") or [{}])[0]
    summary = cate.get("summary", {})
    niche = cate.get("niche") or summary.get("niche") or "launch"
    city_dist = summary.get("effective_city_dist", {})

    cities, unmapped = build_cities(city_dist)
    souls = build_souls(who.get("persona_quotes", []), cities, niche, daily)

    def p50(name):
        return (metrics.get(name) or {}).get("p50")

    reach, clicks = p50("unique_reach"), p50("trials")
    conv, revenue, payback = p50("adopters"), p50("revenue"), p50("payback")
    kpis = {
        "impressions": reach, "clicks": clicks, "conversions": conv,
        "revenue": revenue, "roi": payback,
        "aov": round(revenue / conv, 2) if conv else None,
        "ctr": round(clicks / reach, 6) if reach else None,
        "cvr": round(conv / clicks, 6) if clicks else None,
    }
    # budget: launch 无顶层 budget → 由 revenue/payback 反推 (payback = revenue/budget)
    budget = round(revenue / payback, 2) if payback else 0.0

    # per_platform: channels_hint (真) 拆分; 单渠道时曝光=reach，roi=payback (比例合成)
    channels = []
    for a in report.get("header", {}).get("assumptions", []):
        if a.get("field") == "channels_hint" and isinstance(a.get("value"), list):
            channels = a["value"]
    if not channels:
        channels = ["(合成)"]
    per_platform = {c: {"impressions": (reach or 0) / len(channels),
                        "roi": round(payback, 4) if payback else 0.0}
                    for c in channels}

    # funnel 占位 (判决面板 M3 改读 metrics 真值)
    funnel = {
        "A1_awareness": _band35(metrics.get("unique_reach", {})),
        "A3_engagement": _band35(metrics.get("trials", {})),
        "A4_conversion": _band35(metrics.get("adopters", {})),
    }

    return {
        "version": 1,
        "meta": {
            "caption": _caption(report),
            "run_timestamp": report.get("_run_timestamp"),  # 由 CLI/调用方注入，禁 Date.now
            "generated_by": "launch_replay_export.py v1",
            "disclaimer": report.get("disclaimer"),
            "grounding_confidence": report.get("grounding_confidence"),
            "peak_day": timeline.get("peak_day"),
            "synthetic_fields": [
                "cities[] (层级占比取 effective_city_dist 真值; 坐标 GAZETTEER; 名额按占比合成)",
                "souls[].t (后端无 timestamp，按扩散曲线确定性合成)",
                "souls[].city (persona 无城市，按 effective_city_dist 加权确定性指派)",
                "souls[].sentiment (persona 无情绪，按 purchase_intent_7d 分档派生)",
                "souls[].persona (niche·tier 派生短标签)",
                "kols[] (launch 报告无 KOL 块，默认空; 引爆幕降级)",
                "per_platform (channels_hint 真; 曝光/ROI 比例合成)",
                "funnel_percentiles (占位; 判决面板已改读 metrics 真值)",
                "budget (launch 无顶层 budget，由 revenue/payback 反推)",
            ],
        },
        "budget": budget,
        "platform_alloc": {c: round(1.0 / len(channels), 4) for c in channels},
        "kpis": kpis,
        "funnel_percentiles": funnel,
        "per_platform": per_platform,
        "days": len(daily),
        "daily_total": daily,
        "peak_day": timeline.get("peak_day"),
        "half_life": timeline.get("half_life"),
        "saturation_date": timeline.get("saturation_date"),
        "market_potential_m": timeline.get("market_potential_m"),
        "organic_share": None,       # launch 无 有机/付费 拆分
        "branching_ratio": None,
        "sentiment": {
            "net_sentiment_score": None,
            "high_intent_pct": _high_intent(who.get("persona_quotes", [])),
            "key_opinion_themes": [{"theme": t, "count": 1}
                                   for t in (who.get("objections_as_risk") or [])[:3]],
        },
        "cities": cities,
        "unmapped_cities": unmapped,
        "kols": [],                  # DECISIONS D3
        "souls": souls,
        # 判决面板 (决策 B) 与诚实层消费的 launch 原生块，原样直通:
        "metrics": metrics,
        "intervention_cards": breaks.get("intervention_cards", []),
        "audit_risk": breaks.get("audit_risk"),
        "objections_as_risk": who.get("objections_as_risk", []),
        "season_window": breaks.get("season_window"),
    }


def _caption(report):
    for a in report.get("header", {}).get("assumptions", []):
        if a.get("field") == "product_name":
            return a.get("value")
    return None


def _high_intent(quotes):
    if not quotes:
        return 0.0
    hi = sum(1 for q in quotes if (q.get("purchase_intent_7d") or 0) >= 0.5)
    return round(hi / len(quotes), 4)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", nargs="?", default=str(DEFAULT_INPUT),
                    help="LaunchReport JSON (默认 fixtures/launch_sample.json)")
    ap.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT),
                    help="replay.json 输出路径")
    ap.add_argument("--run-timestamp", default=None,
                    help="注入 meta.run_timestamp (禁 Date.now，保确定性)")
    args = ap.parse_args(argv)

    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.run_timestamp:
        report["_run_timestamp"] = args.run_timestamp
    out = export(report)
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"replay.json -> {args.output}")
    print(f"  days={out['days']} cities={len(out['cities'])} "
          f"kols={len(out['kols'])} souls={len(out['souls'])} "
          f"intervention_cards={len(out['intervention_cards'])}")
    if out["unmapped_cities"]:
        print(f"  [warn] 层级名额不足: {out['unmapped_cities']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
