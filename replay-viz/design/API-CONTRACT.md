# Augur — 后端 API 契约

设计阶段：让 Claude Design 知道有哪些字段、什么量级（但绑定数据请用 `sample-data.json`）。
回传阶段：我（Claude Code）照这份把设计接到真后端。**契约不可改**——后端是现成的。

- 后端基址：`http://<host>:8001`
- 前端选端口：`?api=<port>` 或 `localStorage.osim_api_port`，默认 `8001`
- 静态前端默认端口 8090

## 主端点 · `POST /api/predict`（30–120s，驱动整个仪表盘）

请求体关键字段：
```jsonc
{
  "creative": { "caption": "string", "duration_sec": 15,
                "visual_style": "bright|dark|minimal|flashy",
                "music_mood": "upbeat|calm|asmr|dramatic", "has_celeb": false },
  "total_budget": 80000,
  "platform_alloc": { "douyin": 0.6, "xhs": 0.4 },
  "kol_niche": "beauty",          // 美妆/母婴/数码/美食/穿搭/健身/理财/旅行 英文键
  "use_llm": false,               // true=真LLM灵魂; false=模板(快)
  "llm_calibrate": true,
  "n_souls": 60,                  // 0~10000
  "lifecycle_days": 14,
  "daypart": "auto|morning|noon|afternoon|evening|late",
  "sentiment": "neutral|crisis|negative|positive|viral",
  "audience_age_buckets": null, "audience_gender": null, "audience_city_tiers": null,
  "enable_crossplat": true, "enable_discourse": false, "enable_groupchat": false,
  "enable_brand_memory": false, "enable_recsys_rl": false
}
```

响应顶层 10 键（完整见 `sample-data-full.json`）：

| 键 | 类型/内容 | 驱动 UI |
|----|-----------|---------|
| `scenario_summary` | creative_id, caption, total_budget, platform_alloc | 顶部回显 |
| `kpis` | impressions, clicks, conversions, cost, revenue, ctr, cvr, roi | 主 KPI 网格 |
| `per_platform` | `douyin`/`xhs` → 各 16 字段，含 `*_std` | 分平台表 + 误差条 |
| `macro` | today, holiday{label,lift}, daypart{label,ctr_mult,cvr_mult}, ctr_macro_lift, cvr_macro_lift, llm_calibration{...}, creative_audit_risk, creative_aigc_score | 宏观因子条 |
| `soul_quotes[]` | persona_id, persona_oneliner, persona_card, will_click, reason, comment, feel, purchase_intent_7d, source | 灵魂语录卡 |
| `predicted_sentiment` | sentiment_distribution{positive,neutral,negative}, net_sentiment_score, high_intent_pct, avg_purchase_intent_7d, feel_breakdown{}, key_opinion_themes[], agent_count, llm_backed | 右栏情感面板 |
| `lifecycle` | days, day_axis[14], paid_daily[14], organic_daily[14], total_daily[14], branching_ratio, peak_day, organic_share | Hawkes 曲线 |
| `dag` | n_nodes(64), n_edges(117), nodes[], edges[], intervenable[], layers[8], stats | DAG 图（占位/移植） |
| `extras` | 条件出现：cross_platform / group_chat / discourse / brand_memory / recsys_rl | 前沿分析视图 |
| `schema_outputs` | 17 块：T1_A1_funnel_beta_fit … T3_A7_content_type_coefficient, report_market_insight, report_strategy_case | 结构化输出视图 |

## 沙盘（反事实交互）

| 端点 | 作用 | 返回 |
|------|------|------|
| `POST /api/sandbox/session` | 建会话 | `{ id, baseline_kpis, baseline_result, current, ... }` |
| `PATCH /api/sandbox/session/{sid}` | 改 total_budget / platform_alloc | 更新后的 snapshot |
| `POST /api/sandbox/session/{sid}/counterfactual` | 对比 | `{ baseline_kpis, counterfactual_kpis, delta, cate[] }` |
| `GET /api/sandbox/session/{sid}/lifecycle?days=14` | 重算扩散 | lifecycle 结构 |
| `POST /api/sandbox/session/{sid}/explain?n=&use_llm=` | 重采样语录 | `{ soul_quotes: [...] }` |

`cate[]` 每项：`{ subgroup, effect, stderr }`（如 subgroup="age:25-34"）。

## 其他端点

| 端点 | 返回 | 用途 |
|------|------|------|
| `GET /api/health` | `{ population, souls, kols, llm:{mode,model,api_key_set} }` | 顶栏状态 |
| `GET /api/society/sample?n=10000` | `{ n_total, points:[{x,y,tier,gender,age,is_soul,pid}] }` | 星图 |
| `GET /api/dag` | 因果图 JSON | DAG 视图 |
| `GET /api/platforms` | 各平台 CPM / 冷启动天数 | 参数提示 |
| `GET /api/world` | 当前宏观事件（节假日/天气/舆情） | 宏观条 |
| `GET /api/fan_profile/{niche}` | KOL 粉丝画像 | 领域选择 |

## CORS
后端默认放行 8090/8091/8092/8094/8001。局域网访问要带对应 origin，或设 `OSIM_CORS_ORIGINS` 环境变量。
