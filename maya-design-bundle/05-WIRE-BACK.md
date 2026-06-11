# Maya — 回传接线说明（给 Claude Code / 我）

> 你从 claude.ai/design 拿到设计产物后，把它放进本仓库，然后对我说：
> 「按 `maya-design-bundle/05-WIRE-BACK.md` 把 Maya 新前端接后端跑通。」

## 我会按这个顺序做

### 1. 落地设计产物
- 把 Claude Design 导出的 HTML/React 放到 `frontend-maya/`（新目录，不覆盖旧 `frontend/`，方便回退对比）
- 如果是 React/Vite 工程：`npm install && npm run build`，产物在 `frontend-maya/dist/`
- 如果是 standalone HTML：直接作为静态目录

### 2. 接真后端（契约见 `03-API-CONTRACT.md`）
- 把设计里的 mock 数据替换成对 `http://<host>:8001/api/*` 的真实 fetch
- 接线优先级：
  1. `POST /api/predict` → 主仪表盘（KPI / lifecycle / soul_quotes / predicted_sentiment / macro）
  2. sandbox 会话流 → 反事实滑块 + CATE
  3. `GET /api/health` → 顶栏状态
  4. `GET /api/society/sample`、`GET /api/dag` → 那两个占位视图
- base URL 沿用现有规则：`?api=<port>` / `localStorage.osim_api_port` / 默认 8001

### 3. 移植 3 块重型可视化（Claude Design 做不了的）
从旧 `frontend/js/` 把已调好的模块搬进新壳，用容器节点/ref 挂载：
- `society.js` — 百万 agent WebGL 星图
- `cascade.js` — 首屏舆论级联动画
- 因果 DAG 渲染（旧 `app.js` 里）
> 不重写，只做「挂载适配」——它们已经能跑。

### 4. 改服务脚本 + 起服务验证
- `run-oransim.ps1`：把 `--directory frontend` 改成 `--directory frontend-maya`（或 `frontend-maya/dist`）
- 起后端 + 前端，跑 `/api/health` 确认 ok
- 局域网验证：`http://<LAN-IP>:8090`（当前机器约 192.168.x.x）
- 必要时加防火墙放行 8090/8001

### 5. 品牌名核对
- 全局确认界面无 "oransim" 残留，统一为 **Maya**
- 页面 `<title>`、favicon、顶栏 logo、loading 文案都改成 Maya

## 验收清单
- [ ] 打开新前端，顶栏 health 显示「10万消费者 / 100 灵魂 / LLM 在线」
- [ ] 点「开始预演」→ 真实 KPI 出来（不是 mock）
- [ ] 拖反事实滑块 → KPI delta + CATE 实时变
- [ ] Hawkes 曲线、灵魂语录、情感面板都接的是真数据
- [ ] 星图 / DAG 两个占位视图接上现有模块
- [ ] 局域网另一台机器能打开
- [ ] 全站无 oransim 字样

## 备注
- 后端代码无需改动（除非新设计要新字段——那再说）。
- 旧 `frontend/` 保留作回退，确认新版稳定后再决定删不删。
