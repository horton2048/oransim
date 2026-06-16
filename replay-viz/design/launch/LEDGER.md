# 上市回放前端 · LEDGER（循环执行状态 / 单一事实源）

> 每轮：读「当前指针」→ 做下一个未完成 AT → 验收闸绿 → 回写本表 → commit（引用 AT 编号，mod/dev，fork 工作流）。
> 一里程碑全绿再进下一个。歧义按四条铁律自决、DECISIONS 记一行；产品级标「⚠待复核」继续不停等。
> 详规：`00-工作流总纲.md` / `01-开发规范.md` / `02-验收规范.md`。

---

## 当前指针
→ **FE-M7 真 LLM 全量接入 · 已通（2026-06-16）**。用户要求「全量接这个模型，把 think 关掉」。换 provider 为 **Agnes AI**（OpenAI 兼容免费网关，`agnes-2.0-flash` 非推理无 `<think>`，~1.5s）。三处接通：抽取(LLM)、souls 放开(`use_llm=ov.use_llm` + C端发 `use_llm:true`)、新增 launch 版 LLM soul `soul_infer_llm_launch`(产 will_try/would_pay/objection)。修两 bug：extract 解包模型偶发的 `{value,provenance}` 字段(D27)；diorama 对 beverage 等无 fan-prior 品类回退 demo→注入基础人口城市分布(D26)。真机 e2e 自验全通：咖啡→真 LLM 抽取出目标用户/卖点→souls 意向 0.0–0.6 真实分布+persona 化 objection→结果卡→回放出 24 真城市(非散粉 demo)。新增 test_launch_soul_llm 3/3 + launch 回归 18/18(mock)。截图 evidence/llm-result-card.jpeg / llm-diorama-fixed.jpeg。**⚠ 关键待复核(D27)：会火指数反而从 mock 的 33 降到 ~26——souls 从通用人群抽样且不认受众(D25)，意向被非目标人拉低；要真正体现「聪明」须让 souls 按受众采样。** 另：全量 pytest 有 1 个**先前就存在**的失败 `test_launch_m0_regression`(campaign predict KOL 并列排序非确定，stash 我的改动后仍挂，与本次无关)。

### FE-M6 C端网页产品 · 首版已通（2026-06-15）
→ **FE-M6 C端网页产品 · 首版已通（2026-06-15）**。用户方向（AskUserQuestion）：目标=独立创业者/小品牌主「测能不能火」；交互=落地页→一键揭幕→结果卡；diorama=核心卖点。产出 `launch-c.html`：hero 输入→揭幕动画→结果卡（会火指数★+触达/采纳/营收+锐评+最大阻力(objection原话)+反事实关键变量+看回放+分享卡）→「看电影回放」拉 diorama。真后端 e2e 自验全通（hero→结果卡→回放同 spec）。截图 evidence/c-hero.jpeg / c-result.jpeg。launch-console.html(操作台版)保留为 pro 版。⚠待打磨：会火指数公式偏低（mock 意向低→多数想法 24-40 分，见 DECISIONS D23）；分享=复制文案/截图（最小，D24）。

### FE-M6 += 结构化人群定向（2026-06-15，后端增量+前端，DONE）
- 后端：SimulateOverrides 加 audience_age_buckets/gender/city_tiers；compile_spec 加 audience_override（按值 intern）；_simulate_sync 注入 AudienceFilter。复用世界模型软定向(命中×2/其余÷2)。tests/test_launch_audience.py 4/4，回归 28/28。
- 前端：launch-c「🎯 细调目标人群」可展开区（性别单选 + 年龄/城市多选 chips）→ readAudience()→ overrides。
- e2e 自验：面膜 定向女 采纳51/营收¥2.3k vs 定向男 采纳21/营收¥926（2.4×，方向合理）。截图 evidence/c-audience-tune.jpeg。
- 见 DECISIONS D25。⚠待复核：souls/会火指数对定向不敏感（souls 采样未按受众）。

### FE-M5 上市操作台 · DONE（2026-06-15）
北极星达成：launch-console.html = v4 视觉 + launch 真数据 + 真后端 + 揭幕动画，想法→后端→全卡片→回放全 Playwright 自验。打磨全清（采纳率精度/消字体404/星点动画）。可选「得意黑自托管」**主动放弃**（=404 的 Smiley Sans，两 CDN 路径皆死、sourcing 是 rabbit hole、CJK 字体数MB 撑仓库、Noto 回退已够好）。cron 已停（达成终止条件，再跑空转）。后续仅人工：验收/commit。**⚠ M4「挂进 frontend/ campaign SPA」作废——宿主=独立 launch-console.html。**

### FE-M5 · 上市操作台（launch-console.html）
- [x] v4 视觉/布局复刻（复用 v4 `<head>` CSS 逐字；topbar/三栏/琥珀主题）
- [x] 左面板：上市想法输入 + 预设4 + 预算/样本/seed/horizon 滑块 + 开始预演
- [x] 真后端贯通：ingest→spec_id→simulate(overrides)→LaunchReport（fetch().json() 直消费流式）
- [x] KPI 6卡：触达/试用/采纳/采纳率/营收/回本（P50+P35/P65带）
- [x] 90天Bass曲线（峰/半衰/饱和/潜在盘）
- [x] 指标分位带（替五阶漏斗）4条
- [x] 敏感性龙卷风=干预卡Δ采纳 3
- [x] 命名干预卡（替KOL优选）3
- [x] 市场洞察报告（假设三色源+免责+置信）
- [x] 右栏 AI民意（高购意占比）+ 证词墙（persona objection 逐字，8条）
- [x] 渠道/宏观降级卡（标 stub/未校准）
- [x] 「开始回放」→ diorama overlay（iframe v3 `?session=spec_id`，同 spec 实测）
- [x] Playwright 真后端 e2e 自验（护肤精华→全卡片填充→回放同 spec）；截图 evidence/m5-launch-console-{idle,filled}.jpeg
- [x] 打磨①：采纳率自适应精度（0.0%→0.16‱，新增 rate() 万分比兜底）— Playwright 自验
- [x] 打磨②：下半屏卡片视觉核验（指标分位带/龙卷风Δ/命名干预卡/渠道/宏观/报告全正确渲染）— 截图 evidence/m5-...-lowerhalf.jpeg
- [x] 用户确认方向「是我要的」（2026-06-15）
- [x] 打磨③：删死 Smiley @font-face（两个 jsdelivr CDN 均 404，v4 本就回退 Noto）→ console **0 报错**，显示字体回退 Noto，视觉无变化 — Playwright 自验（evidence/m5-...-nofont404.jpeg）
- [x] 打磨④：开跑星点 reveal 动画（照 v4 + 最短 1.8s 仪式感，因真后端可能 <1s）。程序化自验：650ms 时 overlay 在/计数器 38517/进度 19%/13 星点亮 → 跑满 → 揭幕填充态
- **FE-M5 核心 + 全 v4 保真项完成**。剩可选：得意黑显示字体自托管（D20，纯观感）
- [ ] 打磨待办（cron 续做，可选）：得意黑 woff2 自托管
- 产出：`replay-viz/app/launch-console.html`（+ frontend/replay/ 落位）；evidence/m5-launch-console-{idle,filled,lowerhalf}.jpeg

## 上轮结束于
字体降级栈完成（2026-06-13，Playwright 自验）：v3 三套字体 var 补优秀系统 CJK 回退（sans→PingFang SC/Microsoft YaHei/Source Han/system-ui；serif→Source Han Serif/Songti/SimSun；mono→ui-monospace/Cascadia/Consolas）。Google Fonts 留作渐进增强，挂了/离线回退好字体而非通用 sans。实测 body 计算栈含系统 CJK、engineUp、渲染正常。自决：CJK 全量自托管过重（数 MB woff2），取扎实降级栈，全量 subset 自托管标待复核。

## 全局阻塞
（无）

---

## 里程碑 / AT 清单

### FE-M0 · 地基  ✅ DONE
- [x] 抓真实 `LaunchReport` → `fixtures/launch_sample.json`（`scripts/capture_launch_sample.py`）
- [x] 真实数据 ↔ v3 消费契约对照表（总纲 §2）
- [x] 架构决策 A/B（总纲 §3，DECISIONS D1）

### FE-M1 · 适配器  ✅ DONE（2026-06-12）
- [x] AT-FE-1-01 确定性（逐字节双跑一致）
- [x] AT-FE-1-02 黄金一致
- [x] AT-FE-1-03 过 validReplay
- [x] AT-FE-1-04 脊柱真值不被篡改
- [x] AT-FE-1-05 分位带直通
- [x] AT-FE-1-06 干预卡直通
- [x] AT-FE-1-07 合成字段全打标
- [x] AT-FE-1-08 城市层级守真
- [x] AT-FE-1-09 证词原话逐字
- [x] AT-FE-1-10 sentiment 派生口径
- [x] AT-FE-1-11 诚实元上屏可用
- [x] AT-FE-1-12 合成确定性
- 产出：`replay-viz/launch_replay_export.py` + `tests/test_launch_replay_export.py` + `fixtures/launch_replay.golden.json`

### FE-M2 · 接 v3 取数  ✅ DONE（2026-06-12，Playwright 自验）
- [x] AT-FE-2-01 fetch 通路（只 fetch launch-replay.json，未回退；网络记录佐证）
- [x] AT-FE-2-02 点阵非空（11706 采样点 / 25 城）
- [x] AT-FE-2-03 五幕可播（I→II→III→IV→V 全推进，判决面板渲染零崩）
- [x] AT-FE-2-04 时间轴（90 天轴，seek 可用）
- [~] AT-FE-2-05 证词卡：souls 数据流已证（objection 原话进判决口碑、5 灵魂）；**WebGL 点击弹卡未自动化**（同 campaign 已测渲染码），留 M3 截图旁证
- [x] AT-FE-2-06 离线兜底（404→回退内嵌 60-soul demo，引擎起、不黑屏）
- 产出：v3 `?data=` 薄改 + `app/launch-replay.json` + 截图 `m2-launch-verdict.jpeg`

### FE-M3 · 判决面板纠偏(B)  ✅ DONE（2026-06-12，Playwright 自验）
- [x] AT-FE-3-01 标签纠偏（触达/试用/采纳/营收 + P35/P65，无 A1/p25 残留）
- [x] AT-FE-3-02 读真 metrics（472.7k/139/28/¥1.2k 直读 metrics）
- [x] AT-FE-3-03 弱字段标注（per_platform ROI「—」、净情绪「—」，不编造）
- [x] AT-FE-3-04 第五幕旁白（P35/P50/P65 + 潜在盘 160；ACT II/IV 也改 launch 感知）
- [x] AT-FE-3-05 campaign 不回归（旧标签/ROI/14日 完好）
- 产出：v3 `showVerdict`+`bandHTML`+ACTS 薄改（metrics 分支）；适配器补 half_life/saturation_date/market_potential_m + 黄金重冻

### FE-M4 · 并入主 SPA  ✅ DONE（2026-06-12，含真后端 e2e 自验）
- [x] AT-FE-4-01 挂载第 10 tab（iframe 在 SPA 内加载 v3 launch 回放，Playwright 自验）
- [x] AT-FE-4-02 数据贯通（`GET /api/launch/replay/{spec_id}` 路由 + v3 `?session=` 分支；真 uvicorn e2e：ingest→spec_id→v3 fetch 后端→渲染 launch）
- [x] AT-FE-4-03 资产落位（app/ 四件→frontend/replay/，iframe 正常加载）
  - [~] Three.js 自托管 vendor/three/ — 延后（D12；当前 CDN，e2e 时 unpkg 地球贴图断证实风险，断网走内嵌兜底）
- [x] AT-FE-4-04 不回归（10 tab、切换正常、零新增 console 错）
- [x] AT-FE-4-05 R5 确认（store 持 spec、报告 `_simulate_sync` 确定性重建，不需 session 缓存报告；路由 e2e 佐证）
- 产出：frontend/replay/（4件）+ index.html（tab+iframe）+ tabs.js（懒加载）+ launch.py（replay 路由）+ v3 `?session=` 分支 + tests/ 路由 e2e + 3 截图
- ⚠ 余 D14：主 SPA 是 campaign 流，无 launch spec_id 源 → 回放 tab 现载静态 demo；自动喂本次 launch 推演需产品决策（SPA 加 launch 入口 / 回放 tab 自带 idea 输入）

---

## 进度速览
| 里程碑 | 状态 | 验收闸 |
|---|---|---|
| FE-M0 地基 | ✅ DONE | 人工核对 |
| FE-M1 适配器 | ✅ DONE | pytest 12/12 |
| FE-M2 接取数 | ✅ DONE | Playwright 5/6 自验 + 1 旁证 |
| FE-M3 判决纠偏 | ✅ DONE | Playwright 5/5 自验 |
| FE-M4 并入 SPA | ✅ DONE | Playwright + 真后端 e2e；pytest 13/13 |
