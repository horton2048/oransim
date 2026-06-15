# 上市回放前端 · LEDGER（循环执行状态 / 单一事实源）

> 每轮：读「当前指针」→ 做下一个未完成 AT → 验收闸绿 → 回写本表 → commit（引用 AT 编号，mod/dev，fork 工作流）。
> 一里程碑全绿再进下一个。歧义按四条铁律自决、DECISIONS 记一行；产品级标「⚠待复核」继续不停等。
> 详规：`00-工作流总纲.md` / `01-开发规范.md` / `02-验收规范.md`。

---

## 当前指针
→ **全部完成（2026-06-13）**：M1–M4 命名 AT + 自驱 backlog（D9/D11/D12/D14/D15 + 字体）全清。自驱循环无剩余可推进项 → cron 已停。后续仅人工决策项：commit/归档、产品级 ⚠待复核（见 DECISIONS）、生产硬化（独立 wheel 打包 / 公网全离线字体 subset）。

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
