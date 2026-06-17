# replay-viz — Augur 前端样板（操作台 + 战况回放）

Augur 推演结果的产品前端定稿样板。**纯前端、不连后端、内嵌真实响应样本**：操作台输入投放 brief → 预演 → 结果仪表盘 → 一键进入电影式战况回放。形式已定稿（2026-06-12），历史探索材料（v1/v2 原型、早期前端原型、调研归档）已清理，备份在 `%TEMP%\replay-viz-pre-cleanup-2026-06-12.zip`。

## 目录

```
replay-viz/
├── README.md            ← 本文件
├── NEXT.md              ← 剩余工作（第 3 刀：接真后端并入主 SPA）
├── replay_export.py     转换逻辑唯一源：/api/predict 响应 → replay.json
│                        （CLI + 可被后端 import 的纯函数 export()）
├── app/                 ★ 前端样板本体
│   ├── v4-console.html  操作台：brief 输入 / 预演 / 仪表盘 /「▶ 战况回放」
│   ├── v3-final.html    战况回放：地球→微缩景观→五幕→判决（v4 以 iframe 拉起）
│   └── replay.json      回放数据（由 fixtures 经 replay_export.py 生成，确定性）
├── fixtures/
│   └── sample-data-full.json   真实 /api/predict 完整响应（112KB，唯一数据源头）
└── design/
    ├── 开发文档.md       施工图（架构 / 契约 / 第 3 刀任务分解 / 风险）
    └── API-CONTRACT.md   后端字段契约
```

## 怎么跑

```powershell
python -m http.server 8124 --directory C:\Users\huang\projects\oransim
# 入口： http://localhost:8124/replay-viz/app/v4-console.html
```

双击 file:// 直接打开两个 HTML 也能跑（数据已内嵌）。v3 单独打开时：加 `?demo=1` 强制内嵌演示数据，不加则 fetch 同目录 `replay.json`。需联网加载 Three.js（unpkg CDN，4s 超时有诚实报错卡）。

## 数据真假口径（诚实层）

- 两个页面内嵌的都是**真实 `/api/predict` 响应**的形状与数值；KPI/漏斗 p25/p50/p75/平台/灵魂语录全是样本真值。
- 合成部分均显式打标：灵魂证词时刻（后端暂无 timestamp，按扩散曲线确定性合成，卡上有微标）、KOL 的平台/起爆日/城市、操作台滑块联动（「确定性演算，非重新推演」）。页内「ⓘ 关于」角标有完整清单。
- 一切转换都确定性可复现：同输入 → 逐字节同输出。

## 改数据

```powershell
python -X utf8 replay_export.py            # fixtures → app/replay.json
python -X utf8 replay_export.py 新响应.json -o app/replay.json
```

v4 的内嵌数据 = `fixtures/sample-data-full.json` 原样；换样本需同步页内 `<script id="oransim-data">` 段。

剩余工作见 `NEXT.md`（接真后端），施工细节见 `design/开发文档.md`。
