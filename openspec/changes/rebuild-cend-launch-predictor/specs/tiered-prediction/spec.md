## ADDED Requirements

### Requirement: 统一预测信封

无论哪一档,系统 SHALL 返回带统一元字段的结果信封:`tier`(A/B/C 之一)、`grounding_confidence`、以及逐字免责声明("这是带标注不确定性的情景推演，不是预测")。

#### Scenario: 任一档结果都带元字段
- **WHEN** 任意一档预测完成
- **THEN** 响应顶层含 `tier` ∈ {A,B,C}、`grounding_confidence`、`disclaimer`

### Requirement: A 档全结构化模拟

A 档 SHALL 复用现有引擎产出完整结构化报告:KPI 分位带(触达/试用/采纳/营收,P35/P50/P65)、90 天时间线、persona 证词(objection 逐字)、以及可供 diorama 回放的非空城市点阵。

#### Scenario: A 档产出完整结构
- **WHEN** 一个 A 档想法完成模拟
- **THEN** 报告含 `metrics` 分位带 + `timeline` + `who_buys.persona_quotes` + 回放城市非空

### Requirement: B 档同管线但标未校准

B 档 SHALL 走与 A 档相同的引擎管线,但 MUST 在结果上标注"未校准"(如 `calibrated=false`、城市分布 `city_dist_source=base_population`),并在呈现层据此拉宽不确定性区间。

#### Scenario: B 档结果带未校准标记
- **WHEN** 一个 B 档想法完成模拟
- **THEN** 报告仍含结构化 KPI,但携带未校准标记(calibrated=false 或等价 source 标注)

### Requirement: C 档 LLM 定性情景且无伪精确 KPI

C 档 SHALL 由真 LLM 产出定性上市情景,字段包含:市场盘子估计(区间)、买家画像、建议渠道、采纳曲线形状(定性,如"慢热长尾"/"脉冲后衰减")、关键风险。C 档 MUST NOT 输出伪精确的点值 KPI(不得给出"采纳 3861 人"这类数字)。

#### Scenario: C 档产出定性情景
- **WHEN** 一个 C 档想法完成推演
- **THEN** 返回 `scenario` 含 市场盘子区间 / 买家 / 渠道 / 采纳形状 / 风险,且不含点值 KPI 数字

#### Scenario: C 档 LLM 不可用时显式降级
- **WHEN** C 档需调用 LLM 但 LLM 不可用(未配置 / 报错)
- **THEN** 返回显式"暂无法生成情景"的诚实提示,MUST NOT 静默回退成看起来像真预测的占位数字
