# -*- coding: utf-8 -*-
"""replay_export.py — 把一次 /api/predict 响应转成 v2 回放所需的 replay.json。

第 1 刀（见 NEXT.md）：只读响应 JSON，不动推演引擎。完全确定性（无时钟、无随机），
同一输入永远产出同一输出。

用法:
    python replay_export.py [input.json] [-o output.json]

默认输入 fixtures/sample-data-full.json（真实响应 fixture），
默认输出 app/replay.json（v3-final.html 的真件取数路径会 fetch 它）。

诚实声明（与 design/终态说明-v2.md 的自检刀对齐）——输出里哪些是合成的：
  - souls[].t            后端 soul_feedback 尚无 timestamp，按扩散曲线质量分布
                         确定性合成；每条带 t_synthetic=true。后端补字段后自动改用真值。
  - kols[].platform      T2_A1 不含平台，按 platform_alloc 权重确定性分配。
  - kols[].fire_day      T2_A1 不含起爆日，按 reach 排名压进曲线前段。
  - kols[].city          T2_A1 不含城市，按人群权重城市轮转分配。
  - cities[].lat/lng     人口只有城市名，经纬度查内置 gazetteer（地理真值，映射本身非编造）。
以上同时汇总在输出的 meta.synthetic_fields 里，前端展示时据此声明。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "fixtures" / "sample-data-full.json"
DEFAULT_OUTPUT = HERE / "app" / "replay.json"

# 层级 → 城市 → 经纬度映射器（NEXT.md 第 1 刀）。
# 坐标为市中心近似值；层级沿用 v2 原型的口径，新增城市按常用一至五线划分。
GAZETTEER = {
    # name: (lat, lng, tier)
    "北京": (39.90, 116.41, 1), "上海": (31.23, 121.47, 1),
    "广州": (23.13, 113.26, 1), "深圳": (22.54, 114.06, 1),
    "杭州": (30.27, 120.16, 2), "成都": (30.66, 104.07, 2),
    "重庆": (29.56, 106.55, 2), "武汉": (30.59, 114.31, 2),
    "西安": (34.34, 108.94, 2), "苏州": (31.30, 120.58, 2),
    "南京": (32.06, 118.80, 2), "天津": (39.08, 117.20, 2),
    "长沙": (28.23, 112.94, 2), "郑州": (34.75, 113.66, 2),
    "东莞": (23.02, 113.75, 2), "青岛": (36.07, 120.38, 2),
    "沈阳": (41.81, 123.43, 3), "宁波": (29.87, 121.55, 3),
    "昆明": (25.04, 102.71, 3), "福州": (26.08, 119.30, 3),
    "厦门": (24.48, 118.09, 3), "哈尔滨": (45.80, 126.53, 3),
    "济南": (36.65, 117.12, 3), "合肥": (31.86, 117.28, 3),
    "南昌": (28.68, 115.86, 3), "贵阳": (26.65, 106.63, 3),
    "南宁": (22.82, 108.32, 3), "太原": (37.87, 112.55, 3),
    "保定": (38.87, 115.46, 3), "烟台": (37.46, 121.44, 3),
    "石家庄": (38.04, 114.51, 4), "洛阳": (34.62, 112.45, 4),
    "桂林": (25.27, 110.29, 4), "襄阳": (32.01, 112.12, 4),
    "赣州": (25.83, 114.93, 4), "湛江": (21.27, 110.36, 4),
    "呼和浩特": (40.84, 111.75, 4), "兰州": (36.06, 103.83, 4),
    "玉林": (22.63, 110.17, 4), "九江": (29.71, 116.00, 4),
    "达州": (31.21, 107.47, 4), "绵阳": (31.47, 104.68, 4),
    "淮安": (33.61, 119.02, 4), "宿迁": (33.96, 118.28, 4),
    "遵义": (27.73, 106.92, 5), "大理": (25.61, 100.27, 5),
    "银川": (38.49, 106.23, 5), "西宁": (36.62, 101.78, 5),
    "驻马店": (33.01, 114.02, 5), "周口": (33.62, 114.65, 5),
}

# feel → sentiment(-1/0/1)，v2 证词卡用。无感且不点击视为负向。
FEEL_SENTIMENT = {"购买冲动": 1, "心动": 1, "好奇": 0, "无感": -1}


def dicts(seq):
    """只保留 dict 项（精简版样本在列表尾部夹 '... (60 total)' 截断标记）。"""
    return [x for x in (seq or []) if isinstance(x, dict)]


def nums(seq):
    """只保留数值项（同上，数值数组也可能被夹截断标记）。"""
    return [x for x in (seq or []) if isinstance(x, (int, float))]


def stable_frac(key):
    """字符串 → [0,1) 的确定性小数（替代随机数，保证可复现）。"""
    h = hashlib.md5(str(key).encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0x100000000


def curve_time(frac, daily):
    """[0,1) 的分位 → 沿日扩散曲线质量分布的连续时刻（天，0 起）。"""
    total = sum(daily) or 1.0
    target = frac * total
    acc = 0.0
    for day, v in enumerate(daily):
        if acc + v >= target:
            inside = (target - acc) / v if v else 0.0
            return day + inside
        acc += v
    return float(len(daily) - 1)


def build_cities(personas):
    """persona 的 city_name 计数 → [{name,lat,lng,tier,weight}] + 未命中清单。"""
    counts = {}
    for p in personas:
        name = (p.get("city_name") or "").strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    cities, unmapped = [], []
    for name, weight in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        hit = GAZETTEER.get(name)
        if hit:
            lat, lng, tier = hit
            cities.append({"name": name, "lat": lat, "lng": lng,
                           "tier": tier, "weight": weight})
        else:
            unmapped.append({"name": name, "weight": weight})
    return cities, unmapped


def build_souls(quotes, personas, daily):
    """soul_quotes → 证词列表。t 优先取后端 timestamp，缺失则按曲线合成。"""
    city_by_pid = {}
    for p in personas:
        pid = str(p.get("persona_id", "")).replace("persona_", "")
        city_by_pid[pid] = p.get("city_name") or ""
    souls = []
    for q in quotes:
        pid = str(q.get("persona_id", ""))
        ts = q.get("timestamp")  # 后端增量字段，现在还没有
        if ts is not None:
            t, synthetic = float(ts), False
        else:
            t, synthetic = round(curve_time(stable_frac(pid), daily), 2), True
        feel = q.get("feel", "")
        sentiment = FEEL_SENTIMENT.get(feel, 0)
        if sentiment < 0 and q.get("will_click"):
            sentiment = 0
        souls.append({
            "t": t, "t_synthetic": synthetic,
            "persona": q.get("persona_oneliner", ""),
            "city": city_by_pid.get(pid, ""),
            "text": q.get("reason", ""),
            "comment": q.get("comment", ""),
            "feel": feel, "sentiment": sentiment,
            "will_click": bool(q.get("will_click")),
            "purchase_intent_7d": q.get("purchase_intent_7d"),
        })
    souls.sort(key=lambda s: s["t"])
    return souls


def build_kols(selected, platform_alloc, cities, peak_day):
    """T2_A1 selected_kols → 回放用 KOL 列表。平台/起爆日/城市均为确定性合成。"""
    ranked = sorted(selected, key=lambda k: (-(k.get("reach") or 0),
                                             k.get("kol_id", "")))
    platforms = sorted(platform_alloc.items(), key=lambda kv: -kv[1])
    total_w = sum(w for _, w in platforms) or 1.0
    ignite_window = max(3.0, peak_day * 2.0)  # 起爆压进曲线前段
    kols = []
    for rank, k in enumerate(ranked):
        frac = stable_frac(k.get("kol_id", rank))
        # 平台：按预算权重确定性落桶
        acc, plat = 0.0, platforms[-1][0]
        for name, w in platforms:
            acc += w / total_w
            if frac < acc:
                plat = name
                break
        city = cities[rank % len(cities)]["name"] if cities else ""
        kols.append({
            "name": k.get("name", ""), "kol_id": k.get("kol_id", ""),
            "tier": k.get("tier", ""), "niche": k.get("niche", ""),
            "platform": plat, "city": city,
            "fire_day": round(rank / max(1, len(ranked) - 1) * ignite_window, 2),
            "fans": k.get("fans"), "reach": k.get("reach"),
            "cost": k.get("cost"), "roi": k.get("roi"),
        })
    return kols


def export(resp):
    so = resp.get("schema_outputs", {})
    lifecycle = resp.get("lifecycle", {})
    kpis = dict(resp.get("kpis", {}))
    scenario = resp.get("scenario_summary", {})
    daily = nums(lifecycle.get("total_daily"))
    personas = dicts(so.get("T3_A1_agent_persona"))
    conversions = kpis.get("conversions") or 0
    kpis["aov"] = round(kpis.get("revenue", 0) / conversions, 2) if conversions else None

    cities, unmapped = build_cities(personas)
    souls = build_souls(dicts(resp.get("soul_quotes")), personas, daily)
    kol_plan = so.get("T2_A1_kol_mix_optimization") or {}
    kols = build_kols(dicts(kol_plan.get("selected_kols")),
                      scenario.get("platform_alloc", {}),
                      cities, lifecycle.get("peak_day", 2.0))

    funnel = so.get("T1_A2_mc_funnel_prediction") or {}
    percentiles = {k: v for k, v in funnel.items()
                   if isinstance(v, dict) and {"p25", "p50", "p75"} <= set(v)}

    return {
        "version": 1,
        "meta": {
            "creative_id": scenario.get("creative_id"),
            "caption": scenario.get("caption"),
            "run_timestamp": funnel.get("run_timestamp"),
            "generated_by": "replay_export.py v1",
            "synthetic_fields": [
                "souls[].t (后端无 timestamp，按扩散曲线合成)",
                "kols[].platform / fire_day / city (T2_A1 无此字段，确定性合成)",
            ],
        },
        "budget": scenario.get("total_budget"),
        "platform_alloc": scenario.get("platform_alloc", {}),
        "kpis": kpis,
        "funnel_percentiles": percentiles,
        "per_platform": resp.get("per_platform", {}),
        "days": lifecycle.get("days", len(daily)),
        "daily_total": daily,
        "daily_paid": nums(lifecycle.get("paid_daily")),
        "daily_organic": nums(lifecycle.get("organic_daily")),
        "peak_day": lifecycle.get("peak_day"),
        "organic_share": lifecycle.get("organic_share"),
        "branching_ratio": lifecycle.get("branching_ratio"),
        "sentiment": resp.get("predicted_sentiment", {}),
        "cities": cities,
        "unmapped_cities": unmapped,
        "kols": kols,
        "souls": souls,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", nargs="?", default=str(DEFAULT_INPUT),
                    help="/api/predict 响应 JSON（默认用 design-bundle 真实样本）")
    ap.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT),
                    help="replay.json 输出路径")
    args = ap.parse_args(argv)

    resp = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out = export(resp)
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"replay.json -> {args.output}")
    print(f"  days={out['days']} cities={len(out['cities'])} "
          f"kols={len(out['kols'])} souls={len(out['souls'])}")
    if out["unmapped_cities"]:
        names = ", ".join(c["name"] for c in out["unmapped_cities"])
        print(f"  [warn] gazetteer 未命中城市: {names}（已记入 unmapped_cities）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
