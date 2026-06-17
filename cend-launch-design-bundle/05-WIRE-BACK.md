# Augur — 回传接线 & 后端改造说明（给 Claude Code / 我）

> 你从 open-design 拿到选定的设计产物后，把它放进本仓库，然后对我说：
> 「按 `cend-launch-design-bundle/05-WIRE-BACK.md` 把选定前端接后端、并据此改造后端跑通。」

这一步与以往那种「纯接线」不同：本次前端**反向定义**了后端要长出的形态（尤其 B 档放宽规则、C 档全新模块）。所以我会**先接线、再改后端**。

## 我会按这个顺序做

### 1. 落地设计产物
- 把选定的 HTML/产物放到新目录（不覆盖现有 `replay-viz/app/launch-c.html`，便于回退对比）。
- 全局确认无 `oransim` 残留；统一为选定的品牌名。

### 2. 接现状真后端（A 档，先跑通）
- 把设计里的 mock 替换成对 `http://<host>:8001/api/launch/*` 的真实 fetch（契约见 `03-API-CONTRACT.md`）。
- 主流程：`POST /ingest` → `POST /simulate`（A 档 LaunchReport）→ A 档结果卡渲染 → 「看电影回放」走 `GET /replay/{spec_id}` iframe。
- 先确保 **A 档端到端真数据**跑通（这是现状后端就能给的）。

### 3. 据选定前端改造后端（本次重点）
按 `openspec/changes/rebuild-cend-launch-predictor/proposal.md` 的能力清单实现：
- **分诊路由（idea-intake-routing）**：`spec/ground.py` 在**产品层**把「硬拒」改为「路由」——置信度/垂类判定保留，用于决定走 A / B / C，不再直接对用户报「测不了」。
- **B 档（tiered-prediction）**：同 `simulate` 管线，加 `tier:"B"` + `uncalibrated` + 分位带放宽规则（落实 sample-B 里 `band_widened` 的真实系数）。
- **C 档 LLM 情景推演（新模块）**：`ingest` 判为引擎演不了 → 走新建模块，真 LLM（agnes）出 `scenario`（盘子/买家/渠道/采纳形状/风险），**无伪精确 KPI**。`api_schemas` 增档位/情景字段。
- **诚实标注（honest-prediction-labeling）**：档位徽章、置信区间、「推演非预测」声明、来源三色、C 档与 A 档视觉强区分——后端保证字段，前端保证呈现。

### 4. 移植「看电影回放」重型可视化
- diorama 微缩沙盘回放已有现成模块（`replay-viz/`，`GET /api/launch/replay/{spec_id}`）——只做**挂载适配**，不重写。
- C 档无沙盘 → 按设计做降级/隐藏。

### 5. 移除 pro 操作台
- 删除 `launch-console.html` 独立入口及其在 `frontend/replay/`、`replay-viz/app/` 下的副本。

### 6. 测试 + 起服务验证
- 新增：分诊路由 + 三档输出契约 + 诚实标注的验收测试（pytest mock 跑数据线；Playwright 跑像素）。保持仓库根 `tests/`。
- 改服务脚本指向新前端目录；本地 + 局域网起服务，`/api/health` 通。

## 验收清单
- [ ] 落地页输入想法 → 揭幕 → A 档真数据结果卡（非 mock）
- [ ] 弱接地想法 → B 档：未校准徽章 + 放宽区间，视觉降一档底气
- [ ] B2B/线下/新物种想法 → **不再硬拒**，落到 C 档定性情景（无伪精确 KPI）
- [ ] 三档视觉明显区分，C 档不借用 A 档精确数字外观
- [ ] 每屏都有档位徽章 + 置信区间 + 「推演非预测」声明 + 来源三色
- [ ] 「看电影回放」拉起真 diorama；C 档优雅降级
- [ ] pro 操作台入口已移除
- [ ] 局域网另一台机器能打开；全站无 oransim 字样

## 备注
- A 档现状后端可直接用；B 档放宽规则与 C 档模块是新写的，会配验收测试。
- 现有推演引擎（grounding / world-model / Bass diffusion / souls / launch_replay_export）原样复用，不重写。
