## 1. 后端 · 分诊路由 (idea-intake-routing)  ✅ 2026-06-16

- [x] 1.1 写路由测试(red):`tests/test_launch_routing.py` — A/B/C 三类 idea(消费已校准 / 已识别未校准 / B2B 域外)→ 正确 tier;空输入引导非拒绝;同输入同档可复现
- [x] 1.2 实现 `route_idea(ground_result) -> tier`(`spec/route.py`):按 `rejected`/`niche` 映射;niche→fan_prior 别名表(electronics→tech、parenting→mom;beverage/home/pet/v2 判 B);`resolve_prior_niche` 让 A 档真用上校准 prior
- [x] 1.3 `api_routers/launch.py` 编排接入:`ingest` 回带 tier 提示 + 永不 dead-end;`simulate` 按 tier 分派(A/B→`_simulate_sync`,C→情景模块)
- [x] 1.4 路由测试转绿(11 passed)

## 2. 后端 · C 档 LLM 情景 (tiered-prediction C)  ✅ 2026-06-16

- [x] 2.1 写 C 档测试(red,桩 provider 仿 `test_launch_soul_llm`):合并入 `tests/test_launch_routing.py` — scenario 字段齐全、**无点值 KPI**、LLM 不可用 / 坏 JSON 时显式降级(不静默造占位)
- [x] 2.2 实现 `backend/oransim/agents/launch_scenario_llm.py`:LLM → `{market_sizing, buyer_personas, channels, adoption_shape, key_risks}`;严格 JSON 解析 + `<think>` 兜底剥离;不进 Bass/world-model
- [~] 2.3 `api_schemas` 增 C 档响应模型 — 暂以 dict 信封直返(FastAPI 直出 dict, 不阻塞);**后续可补 pydantic 模型**(Checker 待办)
- [x] 2.4 C 档测试转绿

## 3. 后端 · 统一信封 + A/B 标记 (tiered-prediction A/B + envelope)  ✅ 2026-06-16

- [x] 3.1 写信封测试(red):并入 `tests/test_launch_routing.py` — 任一档响应含 `tier`+`disclaimer`;A 档结构完整;B 档带未校准标(`uncalibrated`/`band_widened`)
- [x] 3.2 `LaunchReport` 加顶层 `tier`;B 档未校准标记直通(复用 D26 base_population)+ 分位带放宽(×2.5 真实写入, 非前端伪造)
- [x] 3.3 信封测试转绿;**回归:现有 launch 测试全绿(110 passed / 2 skip)** — 其中 `test_at_m7_05` 按 BREAKING 改写为「B2B→C」

## 4. 前端 · 单一 C 端结果卡按档变形 (cend-experience + honest-prediction-labeling)  ✅ 2026-06-16 (像素验收待 §7)

- [x] 4.1 重做 `replay-viz/app/launch-c.html` 结果卡:按 `rep.tier` 路由渲染(A/B=会火指数环+KPI 卡+90天时间线sparkline+谁会买+反事实干预+回放;C=情景备忘录,**无 KPI 数字块**)。接真 `/api/launch/*`,字段名按真后端实测(非 sample)
- [x] 4.2 档位徽章(A 青/B 琥珀/C 紫)+免责声明常驻;C 档切换到衬线「情景剧本」气质(无仪表数字),强区分于 A;C 市场盘子只给数量级超宽区间
- [x] 4.3 三色假设打标(用户原话/LLM推断/系统默认);persona objection 逐字不润色;B 档「未校准」标 + 放宽系数可见
- [x] 4.4 后端连不上/422/非JSON → 明确提示不空转;C 降级(无LLM)→ 诚实「需真LLM」态不造占位

## 5. 前端 · diorama 回放按档 (cend-experience)  ✅ 2026-06-16 (像素验收待 §7)

- [x] 5.1 A/B 档「看电影回放」拉 `v3-final.html?session=<spec_id>`(后端 replay 路由 A/B 出真城市)
- [x] 5.2 C 档不渲染回放按钮 → 换「本档为定性推演，无微缩沙盘回放」说明(后端 replay/whatif 对 C 亦 422 防御)

## 6. 移除 pro 操作台 + 同步副本  ✅ 2026-06-16

- [x] 6.1 删 `launch-console.html`(两副本); 无代码指向它(仅 design/ 文档历史提及)
- [x] 6.2 `replay-viz/app/`(规范源)→ `frontend/replay/` 复制同步, 两副本 `diff -q` 一致; 全站 0 处 `oransim`

## 7. 验收 (Playwright 像素 + 全量回归 + 对规格自检)  ✅ 2026-06-16

- [x] 7.1 Playwright:A 档想法(面膜精华)走完主线截图 — 校准徽章+会火指数环+KPI 带+Bass 时间线+5 条逐字证词+反事实卡+回放按钮(`evidence/cend-A-card.jpeg`)
- [x] 7.2 Playwright:C 档 B2B SaaS 走完主线 — 实跑 mock 走诚实降级态(`cend-C-degrade.jpeg`);注入真 C 信封验证情景备忘录(`cend-C-scenario.jpeg`):无 KPI grid、无 numerals、无回放、数量级超宽区间、serif 强区分于 A。B 档(气泡水)未校准徽章+×2.5 放宽带(`cend-B-card.jpeg`)
- [x] 7.3 全量 pytest(mock):**217 passed / 4 skip**(skip 为既有 @live);新增路由/C档/信封/守卫测试全绿
- [x] 7.4 像素 Checker 额外发现并修:`/replay`+`/whatif` 对 C 档 KeyError/伪精确 → 422 守卫;占位例「洁面慕斯」误落 C → 补 beauty 洁面类 grounding 词;三档实跑真后端数据(非 mock 编造)
