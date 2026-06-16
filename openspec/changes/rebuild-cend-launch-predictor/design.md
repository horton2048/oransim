## Context

当前系统(`api_routers/launch.py`):`ingest`(extract+ground)→ `simulate`(compile→world-model→Bass→souls→`LaunchReport`)→ 适配器 `launch_replay_export` 出 diorama 数据。`spec/ground.py` 对非消费垂类 / B2B / 置信<0.55 **硬拒绝**。已校准层只有世界模型 + `fan_profile`(8 个 prior)+ KOL 库 + CN 社媒渠道;`diffusion(Bass)` 通用但 p/q/m 未标定。真 LLM = Agnes `agnes-2.0-flash`(非推理、无 `<think>`、~1.5s)已接通。前端两套:C 端 `launch-c.html` + pro `launch-console.html`(双份落在 `replay-viz/app/` 与 `frontend/replay/`)。

**硬约束(业主红线)**:诚实第一(不伪造精确、合成/未校准字段打标、objection 逐字、不动推演引擎内部数学);测试放仓库根 `tests/`(禁 `backend/tests/`);mock 模式 CI 必须绿;`frontend/` 是复制非搬移;真 LLM 非确定不得与字节级黄金冲突(测试跑 mock)。

## Goals / Non-Goals

**Goals:**
- 任意想法 → 一份**诚实分档**的预测(A 校准 / B 未校准 / C LLM 情景),永不对用户硬拒。
- 单一 C 端产品(落地页→揭幕→结果卡→diorama),复用现有引擎。
- 后端改动**加法为主**:A/B 行为不变,现有 launch 测试保持绿。

**Non-Goals:**
- 不为 B2B/服务建真校准引擎(那是 C 档 LLM 定性,非真模拟)。
- 不动 Bass / world-model 数学;不在本次解决 souls 受众感知(D25,另行)。
- 不做多语言、不做账号体系。

## Decisions

### D-1 路由放在产品编排层,`ground()` 保持诚实判定
新增 `route_idea(ground_result) -> tier` 于 `launch.py`(或薄模块),**不改 `ground()` 让它停止拒绝**——恰恰要用它的 `rejected` / `niche` / `confidence` 当分档信号。
- 规则:`not rejected & niche∈fan_priors(含别名 electronics→tech / parenting→mom)` → **A**;`not rejected & niche∉priors` → **B**;`rejected`(b2b / 低置信 / 非消费) → **C**。
- 备选:改 `ground()` 永不拒 → 否决(丢失选 C 档的信号,且污染引擎判定)。

### D-2 C 档 = 新增 LLM 情景模块,与 `_simulate_sync` 并列
新增 `agents/launch_scenario_llm.py`:输入 spec/idea,输出 `scenario` dict(市场盘子区间、买家画像、渠道、采纳形状(定性枚举)、关键风险),**不产点值 KPI、不进 Bass/world-model**。
- 备选:把域外想法塞进现有引擎 → 否决(伪精确,踩红线)。
- LLM 不可用 → 显式降级提示,不静默造占位(对齐 spec C 档场景)。

### D-3 统一响应信封 + 前端按档变形
A/B 仍返回 `LaunchReport` 并加顶层 `tier`;C 返回 `{tier:"C", scenario, grounding_confidence, disclaimer}`。前端结果卡按 `tier` 切换形态(A/B=KPI 卡 + 会火指数 + 回放;C=定性情景卡,无 KPI 数字块)。
- 备选:三套独立接口 → 否决(C 端要统一消费)。

### D-4 B 档复用 A 管线 + 标记,不建新引擎
B 走与 A 相同的 `_simulate_sync`,仅靠已有 `calibrated=false` / `city_dist_source=base_population`(D26 已落)标未校准,呈现层据此拉宽区间、加"未校准"标。

### D-5 前端重做单一 C 端,移除 pro 操作台
重做 `replay-viz/app/launch-c.html` 为唯一产品;`v3-final.html` diorama 复用,C 档隐藏入口;删 `launch-console.html`(两副本)。保持 `replay-viz/app/`(规范源)→ `frontend/replay/`(复制)同步。

### D-6 测试策略:mock + 桩 LLM
路由 + A/B 契约用 mock 模式 pytest;C 档用**桩 provider**(仿 `test_launch_soul_llm`)断言情景字段映射与"无点值 KPI";像素用 Playwright 按档截图。真 LLM 端到端走手动 / `@live` skip-by-default。

## Risks / Trade-offs

- C 档 LLM 编出"看似可信的市场盘子" → 标"未校准 LLM 估计" + 宽区间 + 无精确 KPI + 醒目徽章;绝不当事实陈述。
- 路由误判(消费想法被 ground 拒 → 误入 C) → 规则保守,B 档兜住"识别到但没校准";记录路由决策便于后续调。
- 移除 pro 操作台影响既有依赖 → 它是内部未提交资产,留在 git 历史,可恢复。
- 前端重做回退现有可用 C 端 → 以现 `launch-c.html` 为参照、增量重做、验收测试守门。
- 会火指数仍偏低(D25 souls 不认受众) → 本次不修,明确标注;分档不解决该问题。
- 两份前端漂移 → tasks 内置同步步骤,单一规范源 + 复制。

## Migration Plan

1. 后端加法上线:`route_idea` + C 档模块 + `tier` 字段;A/B 路径不变 → 现有 18 个 launch 测试保持绿。
2. 前端:重做 launch-c(按档变形)+ 删 console;同步两副本。
3. 回滚:还原 `launch.py` 编排 + 前端;推演引擎零改动,风险隔离在产品层。

## Open Questions

- C 档 `scenario` 的精确字段 schema(市场盘子单位?采纳形状用枚举还是自由文?)— 先定 v1,看真实输出再收敛。
- 档位对用户的友好名(A=校准模拟 / B=参考估计 / C=AI 情景推演)?
- B 档是否也给 diorama(现 base-pop 已有城市)?默认 A/B 都给、C 不给。
