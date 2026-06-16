# 会不会火 — 后端数据契约（设计参考 + 回传后接线依据）

> 设计阶段：让 open-design 知道有哪些真实字段（别编）。回传后：我据此把静态设计接到真 `/api/launch/*`。
> **诚实说明**：下表 A 档为**现状真后端**；B 档分诊框架、C 档整档为**本次要建/要改**的后端。前端先定形态，后端据此长出来。

## 现有端点（`backend/oransim/api_routers/launch.py`）

| 方法 | 路径 | 作用 |
|------|------|------|
| `POST` | `/api/launch/ingest` | 抽取 + grounding（不烧仿真，廉价预览）。流式 keepalive。返回 `spec_id` + `assumed_fields` + `grounding_confidence`（**当前：<0.55 硬拒**——本次改为路由到 C 档） |
| `PATCH` | `/api/launch/spec/{id}` | 字段级人工修正，provenance→user_confirmed |
| `POST` | `/api/launch/simulate` | 编译 → 多 seed 蒙特卡洛 → souls(launch, 真 LLM) → diffusion → **LaunchReport**。流式 |
| `GET` | `/api/launch/replay/{spec_id}` | 把推演转成回放前端 `replay.json`，供「看电影回放」iframe 取数 |
| `GET` | `/api/launch/whatif/{spec_id}` | 命名反事实弹药库 |

## LaunchReport 结构（A 档 · 真后端 · 见 `sample-A.json`）

顶层（**每个响应都带这几个诚实标记**）：
```
assumed_fields[]            假设字段清单
grounding_confidence        0–1，接地置信度
disclaimer                  逐字「这是带标注不确定性的情景推演，不是预测」
header { disclaimer, grounding_confidence, assumptions[] }
metrics { ... }
timeline { ... }
who_buys { ... }
what_breaks { ... }
locale, spec_id, n_seeds
```

- **`header.assumptions[]`**：`{field, value, source}`，`source ∈ {用户原话, LLM 推断, 系统默认}` —— **三色标注**的素材。
- **`metrics`**：六个指标 `unique_reach / trials / adopters / adoption_rate / revenue / payback`，每个 `{p35, p50, p65, p35_label:"下行情形", band:true}`（多 seed 经验分位带；单 seed 时退化为 `{p50, band:null, note:"单点、无分位带"}`）。
- **`timeline`**：`daily_adopters[] / daily_revenue[]`（默认 90 点）、`peak_day / half_life / saturation_date / market_potential_m / calibrated`。
- **`who_buys`**：`cate_segments[]`（`summary` 含 `effective_gender_pct_female / effective_age_dist / effective_city_dist`）+ `persona_quotes[]`（`{will_try, would_pay_cny, objection(原话不润色), purchase_intent_7d}`）+ `objections_as_risk[]`。
- **`what_breaks`**：`intervention_cards[]`（`{name, label, delta{}, branch, note}`；竞品卡 `branch:true` 且 label 固定带「这是分支不是预测」前缀）+ `audit_risk` + `season_window`。

## B 档（见 `sample-B.json`）— 同管线，分诊框架待建

- **引擎产出形状 = A**（同一 `simulate` 管线）。
- 本次后端要加的产品层框架：`tier:"B"`、`uncalibrated:true`、`grounding_confidence` 落在弱接地区间（~0.55–0.70）、分位带按规则**放宽**（`band_widened:true`；放宽系数由实现定，sample 用 ×3 示意）、徽章「未校准」。

## C 档（见 `sample-C.json`）— 全新能力，后端尚未实现

- **不复用 `metrics`**。新结构：`tier:"C"`、`no_kpi:true`、`scenario{ market_sizing, buyer_personas[], channels[], adoption_shape, key_risks[] }`、`routed_reason`。
- `market_sizing` 只给**数量级 + 超宽区间**（`magnitude_only:true`）；`adoption_shape` 只给**形状叙事**（`no_numbers:true`）。**红线：C 档不产任何精确 KPI 分位带。**
- 后端实现：`ingest` 判定为引擎演不了（B2B/线下/新物种）→ 路由到新建的 C 档模块，由真 LLM（agnes，`.env` 已接）出定性情景。

## 前端取数约定（回传后我接线时遵循）

- base URL 沿用现有规则：`?api=<port>` / `localStorage` / 默认 `http://<host>:8001`。
- 主流程：`POST /ingest`（拿 `spec_id` + 档位）→ `POST /simulate`（A/B 出 LaunchReport；C 出 scenario）→ 结果卡渲染 → 「看电影回放」走 `GET /replay/{spec_id}` 的 iframe。
- `_bundle_meta` 是本设计包的注释字段，**非后端输出**，接线时忽略。
