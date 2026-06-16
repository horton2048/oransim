## ADDED Requirements

### Requirement: 每份结果带档位徽章与免责声明

系统 SHALL 在每份呈现给用户的结果上显示档位徽章(A/B/C 或其用户友好别名)与逐字免责声明("这是带标注不确定性的情景推演，不是预测")。

#### Scenario: 结果显示徽章与声明
- **WHEN** 任意一档结果展示给用户
- **THEN** 界面可见档位徽章 + "推演非预测"免责声明

### Requirement: C 档视觉与 A 档强区分

C 档结果 SHALL 在视觉上与 A 档明显不同,MUST NOT 借用 A 档的精确 KPI 数字视觉;C 档 MUST 以"未校准 LLM 推演"的显式标识 + 宽区间呈现。

#### Scenario: C 档不穿 A 档的衣服
- **WHEN** 结果为 C 档
- **THEN** 卡片不出现 A 档式精确 KPI 数字块,且带醒目的"未校准 / LLM 推演"标识

### Requirement: 合成与未校准字段打标,真值逐字

系统 SHALL 对合成 / 未校准字段逐个打标(如 B 档城市分布标 `base_population`、C 档情景标"LLM 估计");对真值字段(如 persona 的 objection)MUST 逐字保留、不润色。

#### Scenario: B 档未校准字段打标
- **WHEN** B 档结果使用基础人口城市分布等未校准来源
- **THEN** 该字段携带来源标记(如 `city_dist_source=base_population`)

#### Scenario: 证词逐字不润色
- **WHEN** 结果展示 persona 的 objection / 证词
- **THEN** 文本与引擎产出逐字一致,不被改写润色

### Requirement: 不确定性诚实,不宣称精确

系统 MUST NOT 把任何一档结果呈现为"精确预测";真 LLM 路径(B 档证词 / C 档情景)结果允许逐次浮动,且 C 档区间 SHALL 足够宽以反映其未校准性质。

#### Scenario: 不宣称精确预测
- **WHEN** 任意结果展示
- **THEN** 文案表述为"推演 / 情景 / 带不确定性",无"精确预测 / 保证"类措辞
