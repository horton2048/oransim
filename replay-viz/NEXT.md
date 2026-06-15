# NEXT — 剩余工作：接真后端并入主 SPA（第 3 刀）

2026-06-12 定稿。纯前端样板已完成（`app/v4-console.html` + `app/v3-final.html`，见 README）。前 2.5 刀（数据线 / 回放换真结构 / 操作台）均已完成并经多 agent 审查 + Playwright 实测，过程记录在历史备份 zip 里，此处只留待办。

## 第 3 刀 · 接真后端（动 `frontend/` + 后端轻路由）

1. **后端路由**：`GET /api/replay/{session_id}`，import `replay_export.export()`（转换逻辑唯一源，勿写第二份）。先读 `oransim/api.py` 确认 session 是否持有完整 predict 响应（风险 R5），原则：不动推演引擎。
2. **soul timestamp 小增量**：`soul_feedback` 生成处加 `timestamp` 字段——补上后导出器自动改用真值，证词卡的「时刻为推演合成」微标自动消失（分支已写好）。
3. **前端壳**：主 SPA（`frontend/`，9 个 tab）加第 10 个 tab「🎬 战况回放」：`index.html:226-237` 加按钮 + `<div id="tab-replay">`；`tabs.js:7` 数组加 `"replay"` + 懒加载钩子（首次切入才设 iframe src，拼 `?session=${SESSION_ID}&api=<port>`）；`app.js` `runPredict()` 成功后 postMessage 通知 iframe 刷新。v3 需加对 `?session=` 的取数分支（现仅 demo/replay.json 两级）。
4. **资产落位**：`app/` 两个 HTML 复制进 `frontend/replay/`（:8090 只服务 `frontend/`）；Three.js 自托管到 `frontend/replay/vendor/three/`，importmap 改本地路径（消除 unpkg 依赖）。
5. **操作台去留**：v4 是纯前端 demo 形态；产品里操作台职能由主 SPA 现有面板承担，v4 保留作对外演示件，不并入。

**DoD**：`run-oransim.ps1` 起服务 → 点「预测」→ 切「战况回放」看到本次 predict 的回放（caption 对得上）；断后端时 tab 显示演示水印态；其余 9 个 tab 无回归；局域网另一台机器可用。

## 后续增量（独立排期）

- 12 个裸 schema 的图表化（contract 见 `design/API-CONTRACT.md`）。
- 回放页移动端适配；判决面板置信徽章接真值。
- 已知 minor：v3 暂停态拖时间轴到末端需播放一帧才弹判决；`seek/simT` 未挂 window（影响 e2e 直控）；v4 的 Smiley Sans 字体 CDN 404（有降级，自托管时一并解决）。
