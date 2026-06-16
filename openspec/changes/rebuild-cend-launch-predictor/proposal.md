## Why

现有上市预测是「保安式」守门:只认 15 类消费品、非消费品硬拒绝,产品层还散落两个前端(C 端 `launch-c.html` + pro 操作台 `launch-console.html`),且校准/未校准/伪造三种可信度的数据挤在同一套视觉里,容易让"未校准的猜测"看起来像"精确的预测"。

要把它重构成**一款单一 C 端产品**:用户输入**任何**产品想法都能拿到一份**诚实标注**的上市预测——把"守门人"换成"分诊台",复用已校准的推演引擎,绝不为了"什么都能答"而假装精确。

## What Changes

- **分诊台取代守门人**:任何想法不再硬拒,按可信度分流三档——A 校准模拟 / B 未校准结构化 / C LLM 情景推演。
- **新增 C 档「LLM 情景推演」**:引擎演不了的剧本(B2B / 线下服务 / 全新物种)由真 LLM 出定性推演(市场盘子、买家画像、渠道、采纳曲线形状、关键风险),**超宽区间、无伪精确 KPI**。
- **重做单一 C 端体验**:落地页 → 一键揭幕 → 结果卡 → diorama 回放,响应式;结果卡按档位呈现不同形态。
- **诚实标注合约**:每份结果带档位徽章 + 置信区间 + "推演非预测 / 未校准"声明;C 档视觉与 A 档**明显区分**,绝不混穿;合成 / 未校准字段逐个打标。
- **BREAKING**:原 grounding 对非消费品 / 低置信的**硬拒绝**行为,在产品层改为**路由到 C 档**(引擎内部的领域判定保留,用于决定走 A 还是 C,不再直接对用户报"测不了")。
- **移除** pro 操作台 `launch-console.html` 作为独立入口(及其在 `frontend/replay/`、`replay-viz/app/` 下的副本)。
- **复用不变**:`grounding` / `world-model` / `diffusion(Bass)` / `souls` / `launch_replay_export` 推演引擎原样复用(A、B 档直接用;真 LLM = agnes 已接通)。

## Capabilities

### New Capabilities
- `idea-intake-routing`: 接收任意产品想法,判定其领域与可信度档位(A/B/C)并分流到对应预测路径;**永不硬拒**,总返回一份诚实标注的结果。
- `tiered-prediction`: 三档预测的产出契约——A 复用引擎做全结构化模拟(KPI 分位带 + 时间线 + 证词);B 走同一管线但标"未校准"、拉宽区间;C 走 LLM 出定性情景(盘子 / 买家 / 渠道 / 采纳形状 / 风险),不产伪精确 KPI。
- `cend-experience`: 单一 C 端主线——落地页 → 一键揭幕动画 → 结果卡(随档位变形) → 「看电影回放」拉起 diorama;响应式;此为唯一入口(pro 操作台移除)。
- `honest-prediction-labeling`: 诚实呈现合约——每份结果带档位徽章与置信区间,C 档与 A 档视觉强区分,"推演非预测 / 未校准"声明常驻,合成 / 未校准字段打标;C 档不得借用 A 档的精确数字视觉。

### Modified Capabilities
<!-- openspec/specs/ 为空(本次首次 init),现有系统未以 openspec 规格记录;故无"已记录能力"被修改。grounding 硬拒绝→路由 的行为变更已在 What Changes 标 BREAKING。 -->
(无)

## Impact

- **后端**:`api_routers/launch.py` 编排重做(ingest → 分诊 → 分档 simulate);新增 C 档 LLM 情景推演模块;`api_schemas` 增档位 / 情景字段;`spec/ground.py` 在产品层由"拒绝"改"路由"(引擎判定保留)。复用 `spec/pipeline`、`platforms/.../world_model`、`diffusion`、`agents/soul*`、`launch_replay_export`。
- **前端**:重做 `replay-viz/app/launch-c.html`(单一 C 端,三档结果卡形态);diorama `v3-final.html` 复用并适配(C 档无微缩沙盘时降级 / 隐藏);**移除** `launch-console.html` 及其副本。`frontend/replay/` 与 `replay-viz/app/` 双份保持同步(复制非搬移)。
- **测试**:新增分诊路由 + 三档输出契约 + 诚实标注的验收测试(pytest mock 跑数据线;Playwright 跑像素);保持仓库根 `tests/`,不进 `backend/tests/`。
- **配置**:C 档依赖真 LLM(agnes,`.env` 已接,非推理无 `<think>`)。
- **移除**:pro 操作台入口。
